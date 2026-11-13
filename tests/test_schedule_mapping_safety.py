"""Independent synthetic schedule-mapping regressions; no device contact."""

from __future__ import annotations

from copy import deepcopy
from datetime import time
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bsblan import BSBLAN, BSBLANConfig
from bsblan.exceptions import BSBLANError, BSBLANMalformedResponseError
from bsblan.models import (
    Device,
    ScheduleReadMapping,
    ScheduleSnapshot,
)

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
# Literal firmware-derived variants, not inferred from production constants.
PROFILES = [
    ("heating", 1, ("501", "501.1", "501.2", "501.3", "501.4", "501.5", "501.6")),
    ("heating", 2, ("521", "521.1", "521.2", "521.3", "521.4", "521.5", "521.6")),
    ("hot_water", None, ("561", "561.1", "561.2", "561.3", "561.4", "561.5", "561.6")),
    ("heating", 1, ("502", "502.1", "502.2", "502.3", "502.4", "502.5", "502.6")),
    ("heating", 2, ("522", "522.1", "522.2", "522.3", "522.4", "522.5", "522.6")),
    ("hot_water", None, ("564", "564.1", "564.2", "564.3", "564.4", "564.5", "564.6")),
]


def mapping(ids: tuple[str, ...]) -> ScheduleReadMapping:
    """Construct an explicit mapping from a literal fixture."""
    return ScheduleReadMapping(**dict(zip(DAYS, ids, strict=True)))


def entity(value: str | None = "06:00-07:00", error: int = 0) -> dict[str, Any]:
    """Build a synthetic entity."""
    return {
        "name": "x",
        "value": value,
        "unit": "",
        "desc": "",
        "error": error,
        "dataType": 9,
    }


async def read(
    client: BSBLAN, kind: str, circuit: int | None, profile: ScheduleReadMapping
) -> ScheduleSnapshot:
    """Read the specified group using a caller-configured mapping."""
    if kind == "hot_water":
        return await client.get_hot_water_schedule(mapping=profile)
    return await client.get_heating_schedule(circuit=circuit, mapping=profile)


@pytest.mark.parametrize(("kind", "circuit", "ids"), PROFILES)
async def test_literal_firmware_profiles(mock_bsblan, kind, circuit, ids) -> None:
    """The literal firmware-derived IDs and weekday roles are preserved."""
    response = {
        param: entity(f"{n + 6:02}:00-{n + 7:02}:00") for n, param in enumerate(ids)
    }
    response = dict(reversed(list(response.items())))
    response["999"] = entity()
    request = AsyncMock(return_value=response)
    mock_bsblan._request = request
    result = await read(mock_bsblan, kind, circuit, mapping(ids))
    assert result.complete
    assert result.mapping_source == "explicit"
    assert result.day_assignment == "caller_configured"
    assert len(result.days) == 7
    for n, day in enumerate(DAYS):
        assert result.days[day].parameter_id == ids[n]
        assert result.days[day].schedule.slots[0].start == time(n + 6)
    request.assert_awaited_once_with(params={"Parameter": ",".join(ids)})


@pytest.mark.parametrize(("kind", "circuit", "ids"), PROFILES[3:])
async def test_only_monday_response_is_not_tuesday(
    mock_bsblan, kind, circuit, ids
) -> None:
    """The first ID belongs to Monday, not the old integer-derived day."""
    mock_bsblan._request = AsyncMock(return_value={ids[0]: entity()})
    result = await read(mock_bsblan, kind, circuit, mapping(ids))
    assert result.days["monday"].status == "readable"
    assert result.days["tuesday"].reason_code == "missing"
    assert not result.complete


async def test_same_version_devices_use_only_their_explicit_profiles() -> None:
    """Equal firmware versions do not select a shared schedule profile."""
    first = BSBLAN(BSBLANConfig(host="first.invalid"))
    second = BSBLAN(BSBLANConfig(host="second.invalid"))
    first._firmware_version = second._firmware_version = "5.0.0"
    first._json_api_version = second._json_api_version = "3"
    first._request = AsyncMock(return_value={"501": entity()})
    second._request = AsyncMock(return_value={"502": entity()})
    await first.get_heating_schedule(mapping=mapping(PROFILES[0][2]))
    await second.get_heating_schedule(mapping=mapping(PROFILES[3][2]))
    first._request.assert_awaited_once_with(
        params={"Parameter": "501,501.1,501.2,501.3,501.4,501.5,501.6"}
    )
    second._request.assert_awaited_once_with(
        params={"Parameter": "502,502.1,502.2,502.3,502.4,502.5,502.6"}
    )


@pytest.mark.parametrize(
    ("code", "hint"),
    [
        (7, "requires_reconfiguration"),
        (261, "retry_later"),
        (256, "unknown"),
        (42, "unknown"),
    ],
)
async def test_all_device_errors_keep_context(mock_bsblan, code, hint) -> None:
    """A fully unavailable week preserves all device error context."""
    ids = PROFILES[3][2]
    mock_bsblan._request = AsyncMock(return_value={p: entity(error=code) for p in ids})
    result = await read(mock_bsblan, "heating", 1, mapping(ids))
    assert result.kind == "heating"
    assert result.circuit == 1
    assert not result.complete
    for name, param in zip(DAYS, ids, strict=True):
        day = result.days[name]
        assert (day.parameter_id, day.reason_code, day.error_code, day.retry_hint) == (
            param,
            "device_error",
            code,
            hint,
        )


async def test_device_error_with_non_timeprog_value_remains_unavailable(
    mock_bsblan,
) -> None:
    """An error must not turn a non-TIMEPROG value into a parse failure."""
    ids = PROFILES[3][2]
    failing = entity("5", error=261)
    failing["dataType"] = 1
    mock_bsblan._request = AsyncMock(return_value={ids[0]: failing})
    result = await read(mock_bsblan, "heating", 1, mapping(ids))
    assert result.days["monday"].error_code == 261
    assert result.days["monday"].raw_value == "5"
    assert result.days["monday"].status == "unavailable"


async def test_all_missing_then_recovery(mock_bsblan) -> None:
    """Missing IDs can recover without a negative cache."""
    ids = PROFILES[3][2]
    request = AsyncMock(side_effect=[{"516": entity()}, {ids[0]: entity()}])
    mock_bsblan._request = request
    first = await read(mock_bsblan, "heating", 1, mapping(ids))
    second = await read(mock_bsblan, "heating", 1, mapping(ids))
    assert all(
        day.reason_code == "missing" and day.retry_hint == "unknown"
        for day in first.days.values()
    )
    assert second.days["monday"].status == "readable"
    assert request.await_count == 2
    assert all(
        c.kwargs == {"params": {"Parameter": ",".join(ids)}}
        for c in request.await_args_list
    )


@pytest.mark.parametrize(
    "bad",
    [
        1,
        True,
        "01",
        "0",
        "1.0",
        "1.10",
        "1.01",
        "1,2",
        "1!2",
        " 1",
        "1 ",
        "-1",
        "1.2.3",
    ],
)
def test_mapping_rejects_bad_ids(bad) -> None:
    """Noncanonical and unsafe IDs cannot be configured."""
    values = dict(zip(DAYS, PROFILES[3][2], strict=True))
    values["monday"] = bad
    with pytest.raises(ValidationError):
        ScheduleReadMapping(**values)


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "extra"])
def test_mapping_rejects_bad_shape(mutation) -> None:
    """Exactly seven distinct named days are required."""
    values = dict(zip(DAYS, PROFILES[3][2], strict=True))
    if mutation == "duplicate":
        values["monday"] = values["tuesday"]
    elif mutation == "missing":
        values.pop("sunday")
    else:
        values["holiday"] = "123"
    with pytest.raises(ValidationError):
        ScheduleReadMapping(**values)


async def test_known_pps_with_mapping_fails_before_io(mock_bsblan) -> None:
    """An explicit mapping does not enable unproven PPS support."""
    mock_bsblan._device = Device.model_construct(bus="PPS")
    request = AsyncMock()
    mock_bsblan._request = request
    with pytest.raises(BSBLANError, match="PPS"):
        await read(mock_bsblan, "heating", 1, mapping(PROFILES[3][2]))
    request.assert_not_awaited()


@pytest.mark.parametrize("bad_mapping", ["not a mapping", {"monday": "502"}])
async def test_invalid_mapping_object_fails_before_io(mock_bsblan, bad_mapping) -> None:
    """Reject non-model mappings before the transport is used."""
    request = AsyncMock()
    mock_bsblan._request = request
    with pytest.raises(BSBLANError, match="invalid_mapping") as exc:
        await mock_bsblan.get_heating_schedule(mapping=bad_mapping)
    assert exc.value.kind == "heating"
    assert exc.value.circuit == 1
    request.assert_not_awaited()


async def test_constructed_invalid_mapping_is_revalidated(mock_bsblan) -> None:
    """Pydantic's unchecked constructor cannot bypass pre-I/O validation."""
    values = dict(zip(DAYS, PROFILES[3][2], strict=True))
    values["monday"] = "502!4"
    bad_mapping = ScheduleReadMapping.model_construct(**values)
    request = AsyncMock()
    mock_bsblan._request = request
    with pytest.raises(BSBLANError, match="invalid_mapping") as exc:
        await mock_bsblan.get_heating_schedule(mapping=bad_mapping)
    assert exc.value.__cause__ is not None
    request.assert_not_awaited()


async def test_isolation_and_mutable_observation(mock_bsblan) -> None:
    """Reads and edit copies are independent, but snapshots stay mutable."""
    ids = PROFILES[3][2]
    response = {ids[0]: entity()}
    untouched = deepcopy(response)
    mock_bsblan._request = AsyncMock(return_value=response)
    one = await read(mock_bsblan, "heating", 1, mapping(ids))
    two = await read(mock_bsblan, "heating", 1, mapping(ids))
    assert response == untouched
    original = deepcopy(one.model_dump(mode="json"))
    edit = deepcopy(one.days["monday"].schedule)
    edit.slots[0].start = time(5)
    edit.slots.append(deepcopy(edit.slots[0]))
    response[ids[0]]["name"] = "changed input"
    two.days["monday"].metadata.name = "changed output"
    two.days.pop("tuesday")
    assert one.model_dump(mode="json") == original
    one.days["monday"].schedule.slots.clear()
    assert one.days["monday"].status == "readable"
    assert one.days["monday"].raw_value == "06:00-07:00"


async def test_explicit_read_does_not_change_raw_parameter_access(mock_bsblan) -> None:
    """Generic diagnostic reads do not inherit weekday mapping assertions."""
    ids = PROFILES[3][2]
    request = AsyncMock(return_value={ids[0]: entity(), "501": entity()})
    mock_bsblan._request = request
    await read(mock_bsblan, "heating", 1, mapping(ids))
    request.assert_awaited_once_with(params={"Parameter": ",".join(ids)})
    request.reset_mock()
    await mock_bsblan.read_parameters(["501"])
    request.assert_awaited_once_with(params={"Parameter": "501"})


async def test_context_for_invalid_entity(mock_bsblan) -> None:
    """Malformed days retain group, circuit, weekday, ID and cause."""
    ids = PROFILES[5][2]
    mock_bsblan._request = AsyncMock(return_value={ids[0]: entity("bad")})
    with pytest.raises(
        BSBLANMalformedResponseError, match=r"hot_water.*None.*monday.*564"
    ) as exc:
        await read(mock_bsblan, "hot_water", None, mapping(ids))
    assert exc.value.__cause__ is not None
