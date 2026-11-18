"""A BSB/LPB default write flag is not an individual parameter permission."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bsblan import (
    BSBLAN,
    BSBLANConnectionError,
    BSBLANMalformedResponseError,
    BSBLANScheduleMappingError,
    BSBLANScheduleWriteError,
    BSBLANUnsupportedFeatureError,
    DaySchedule,
    Device,
    EntityInfo,
    ScheduleUpdate,
)
from bsblan._permissions import read_write_permission
from tests.test_schedule_profile_integration import client as automatic_client
from tests.test_schedule_profile_integration import device
from tests.test_schedule_profiles import IDS as PROFILE_IDS
from tests.test_schedule_profiles import controller_data, probe_data
from tests.test_unified_schedules import config, write

DAY = DaySchedule.from_bsblan_format("06:00-08:00")


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({}, None),
        ({"readwrite": 0}, True),
        ({"readwrite": 1}, False),
        ({"readwrite": 2}, False),
        ({"readwrite": 3}, False),
        ({"readwrite": "0"}, False),
        ({"readwrite": False}, False),
        ({"readwrite": True}, False),
        ({"readwrite": None}, False),
        ({"readonly": 0}, True),
        ({"readonly": 1}, False),
        ({"readonly": False}, False),
        ({"readonly": "0"}, False),
        ({"readwrite": 0, "readonly": 1}, False),
        ({"readwrite": 1, "readonly": 0}, False),
        ({"readwrite": 0, "readonly": 0}, True),
    ],
)
def test_raw_permission_flags_are_not_booleans(
    metadata: dict[str, Any], *, expected: bool | None
) -> None:
    """Only explicit integer zero grants readable-and-writable permission."""
    assert read_write_permission(metadata) is expected


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({}, None),
        ({"readwrite": 0}, True),
        ({"readwrite": 1}, False),
        ({"readwrite": 2}, False),
        ({"readonly": 0}, True),
        ({"readonly": 1}, False),
        ({"readwrite": 0, "readonly": 1}, False),
    ],
)
def test_entity_preserves_missing_vs_explicit_permission(
    flags: dict[str, Any], *, expected: bool | None
) -> None:
    """The model's default zero must not manufacture affirmative permission."""
    entity = EntityInfo[float](
        name="Comfort setpoint", unit="°C", desc="", value="21", **flags
    )
    assert entity.read_write_permission is expected


@pytest.mark.parametrize("field", ["readonly", "readwrite"])
@pytest.mark.parametrize("invalid", [False, True, "0", None])
def test_permission_fields_reject_ambiguous_types(field: str, invalid: Any) -> None:
    """Do not coerce false or the string '0' into permission to write."""
    with pytest.raises(ValidationError):
        EntityInfo[float](name="x", unit="", desc="", value="21", **{field: invalid})


@pytest.mark.parametrize("kind", ["heating", "hot_water"])
@pytest.mark.parametrize("bus", ["BSB", "LPB"])
async def test_default_disabled_allows_explicit_parameter_permissions(
    kind: str, bus: str
) -> None:
    """Query exact populated IDs before any /JS; /JC has no value/error fields."""
    client = BSBLAN(config(kind, None if kind == "hot_water" else 1))
    client._device = Device.model_construct(bus=bus, buswritable=0)
    client._request = AsyncMock(
        side_effect=[
            {
                "700.1": {"readwrite": 0, "dataType": 9},
                "700.2": {"readwrite": 0, "dataType": 9},
            },
            {"700.1": {"status": 1}},
            {"700.2": {"status": 1}},
        ]
    )
    await write(client, kind, 1, ScheduleUpdate(tuesday=DAY, wednesday=DAY))
    assert [call.kwargs for call in client._request.await_args_list] == [
        {"base_path": "/JC=700.1,700.2"},
        {
            "base_path": "/JS",
            "data": {"Parameter": "700.1", "Value": "06:00-08:00", "Type": "1"},
        },
        {
            "base_path": "/JS",
            "data": {"Parameter": "700.2", "Value": "06:00-08:00", "Type": "1"},
        },
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"readwrite": 1, "dataType": 9},
        {"readwrite": 2, "dataType": 9},
        {"readwrite": False, "dataType": 9},
        {"readwrite": "0", "dataType": 9},
        {"dataType": 9},
        {"readwrite": 0, "dataType": 0},
        {"readwrite": 0, "dataType": True},
        {"readwrite": 0, "dataType": 9, "error": 7},
        {"readwrite": 0, "dataType": 9, "error": True},
        None,
    ],
)
async def test_later_unknown_or_nonwritable_parameter_blocks_all_writes(
    bad: Any,
) -> None:
    """Every populated day needs positive permission, not only the first day."""
    client = BSBLAN(config())
    client._device = Device.model_construct(bus="BSB", buswritable=0)
    client._request = AsyncMock(
        return_value={
            "700": {"readwrite": 0, "dataType": 9},
            "700.1": bad,
        }
    )
    with pytest.raises(BSBLANUnsupportedFeatureError, match=r"700\.1"):
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY, tuesday=DAY))
    client._request.assert_awaited_once_with(base_path="/JC=700,700.1")


async def test_missing_parameter_permission_is_not_an_override() -> None:
    """An absent structure response must not be interpreted as default readwrite=0."""
    client = BSBLAN(config())
    client._device = Device.model_construct(bus="BSB", buswritable=0)
    client._request = AsyncMock(return_value={})
    with pytest.raises(BSBLANUnsupportedFeatureError):
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY))
    assert client._request.await_count == 1


@pytest.mark.parametrize("response", [[], None])
async def test_malformed_permission_envelope_keeps_classification(
    response: Any,
) -> None:
    """Broken structure data is not a permanent mapping repair."""
    client = BSBLAN(config())
    client._device = Device.model_construct(bus="BSB", buswritable=0)
    client._request = AsyncMock(return_value=response)
    with pytest.raises(BSBLANMalformedResponseError):
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY))


async def test_permission_connection_failure_never_falls_through_to_write() -> None:
    """Temporary transport errors remain retryable and never authorize a command."""
    client = BSBLAN(config())
    client._device = Device.model_construct(bus="BSB", buswritable=0)
    client._request = AsyncMock(side_effect=BSBLANConnectionError())
    with pytest.raises(BSBLANConnectionError):
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY))
    assert client._request.await_count == 1


async def test_target_change_during_structure_probe_aborts_before_writes() -> None:
    """Permission evidence cannot transfer to a different transport endpoint."""
    client = BSBLAN(config())
    client._device = Device.model_construct(bus="BSB", buswritable=0)

    async def request(**_kwargs: Any) -> Any:
        client.config.host = "other.example"
        return {"700": {"readwrite": 0, "dataType": 9}}

    client._request = request
    with pytest.raises(BSBLANScheduleMappingError, match="target_changed"):
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY))


async def test_permission_proof_expires_on_metadata_change() -> None:
    """A proof under disabled defaults must remain bound to its observed target."""
    client = BSBLAN(config())
    client._device = Device.model_construct(bus="BSB", buswritable=0)
    requests = []

    async def request(**kwargs: Any) -> Any:
        requests.append(kwargs)
        if kwargs["base_path"].startswith("/JC="):
            return {
                param: {"readwrite": 0, "dataType": 9} for param in ("700", "700.1")
            }
        client._device.busdest = 99
        return {"700": {"status": 1}}

    client._request = request
    with pytest.raises(BSBLANScheduleWriteError) as err:
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY, tuesday=DAY))
    assert err.value.acknowledged_days == ("monday",)
    assert err.value.failed_day == "tuesday"
    assert len(requests) == 2


async def test_unknown_bus_cannot_override_a_disabled_default() -> None:
    """Only explicitly identified BSB/LPB permits the per-parameter override."""
    client = BSBLAN(config())
    client._device = Device.model_construct(bus=None, buswritable=0)
    client._request = AsyncMock()
    with pytest.raises(BSBLANUnsupportedFeatureError):
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY))
    client._request.assert_not_awaited()


async def test_metadata_change_during_structure_probe_rejects_stale_evidence() -> None:
    """Changing the bus destination invalidates permission proof before /JS."""
    client = BSBLAN(config())
    client._device = Device.model_construct(bus="BSB", buswritable=0)
    calls = []

    async def request(**kwargs: Any) -> Any:
        calls.append(kwargs)
        client._device.busdest = 99
        return {"700": {"readwrite": 0, "dataType": 9}}

    client._request = request
    with pytest.raises(BSBLANUnsupportedFeatureError, match="metadata changed"):
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY))
    assert calls == [{"base_path": "/JC=700"}]


async def test_automatic_write_reuses_fresh_parameter_permission_proof() -> None:
    """A compatible automatic probe with readwrite=0 needs no redundant /JC."""
    client = automatic_client()
    response = {param: {**raw, "readwrite": 0} for param, raw in probe_data().items()}
    client._request = AsyncMock(
        side_effect=[
            device(buswritable=0),
            controller_data(),
            response,
            {PROFILE_IDS[0]: {"status": 1}},
        ]
    )
    await client.set_heating_schedule(ScheduleUpdate(monday=DAY))
    assert client._request.await_count == 4
    assert client._request.await_args_list[-1].kwargs["base_path"] == "/JS"


@pytest.mark.parametrize("flag", [1, 2])
async def test_parameter_denial_wins_over_enabled_defaults(flag: int) -> None:
    """A true gateway indicator does not override a read-only active-table entry."""
    client = automatic_client()
    response = {
        param: {**raw, "readwrite": flag} for param, raw in probe_data().items()
    }
    client._request = AsyncMock(
        side_effect=[device(buswritable=1), controller_data(), response]
    )
    with pytest.raises(BSBLANUnsupportedFeatureError):
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY))
    assert client._request.await_count == 3


async def test_gateway_default_change_expires_even_explicit_automatic_proof() -> None:
    """A permission observed under old gateway settings cannot authorize later days."""
    client = automatic_client()
    replies = iter(
        [
            device(buswritable=1),
            controller_data(),
            {param: {**raw, "readwrite": 0} for param, raw in probe_data().items()},
            {PROFILE_IDS[0]: {"status": 1}},
        ]
    )
    calls = []

    async def request(**kwargs: Any) -> Any:
        calls.append(kwargs)
        if kwargs.get("base_path") == "/JS":
            client._device.buswritable = 0
        return next(replies)

    client._request = request
    with pytest.raises(BSBLANScheduleWriteError) as err:
        await client.set_heating_schedule(ScheduleUpdate(monday=DAY, tuesday=DAY))
    assert err.value.acknowledged_days == ("monday",)
    assert len(calls) == 4
