"""HTTP-boundary regressions for configured schedule observations and writes."""

from __future__ import annotations

import asyncio
import json
from datetime import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from pydantic import ValidationError

from bsblan import BSBLAN, BSBLANConfig
from bsblan.exceptions import (
    BSBLANConnectionError,
    BSBLANInvalidParameterError,
    BSBLANMalformedResponseError,
    BSBLANScheduleMappingError,
    BSBLANScheduleWriteError,
    BSBLANUnsupportedFeatureError,
)
from bsblan.models import Device
from bsblan.schedules import (
    DaySchedule,
    ScheduleMapping,
    ScheduleMappings,
    ScheduleSnapshot,
    ScheduleUpdate,
)

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
IDS = ("700", "700.1", "700.2", "700.3", "700.4", "700.5", "700.6")
QUERY = "700,700.1,700.2,700.3,700.4,700.5,700.6"


def mapping() -> ScheduleMapping:
    """Use a synthetic profile, never a firmware-wide mapping claim."""
    return ScheduleMapping(**dict(zip(DAYS, IDS, strict=True)))


def entity(
    value: Any = "06:00-08:00", *, error: int = 0, data_type: Any = 9
) -> dict[str, Any]:
    """Build a complete synthetic response entity."""
    return {
        "name": "x",
        "value": value,
        "unit": "",
        "desc": "",
        "error": error,
        "dataType": data_type,
    }


def config(kind: str = "heating", circuit: int | None = 1) -> BSBLANConfig:
    """Bind exactly one synthetic group to this target."""
    key = "hot_water" if kind == "hot_water" else f"heating_{circuit}"
    return BSBLANConfig(
        host="example.com", schedule_mappings=ScheduleMappings(**{key: mapping()})
    )


async def read(client: BSBLAN, kind: str, circuit: int | None) -> ScheduleSnapshot:
    """Exercise the two public schedule readers."""
    if kind == "hot_water":
        return await client.hot_water_schedule()
    return await client.heating_schedule(circuit=circuit)


@pytest.mark.parametrize(
    ("kind", "circuit"), [("hot_water", None), ("heating", 1), ("heating", 2)]
)
async def test_read_exact_mapping_and_fresh_values(
    aresponses: ResponsesMockServer, kind, circuit
) -> None:
    """Exact IDs, not response order, assign days and every call fetches anew."""
    requests = []

    async def handler(request: Any) -> Any:
        requests.append((request.path, request.query["Parameter"]))
        text = "06:00-08:00" if len(requests) == 1 else "09:00-10:00"
        return aresponses.Response(
            text=json.dumps(
                {"700.1": entity("##:##-##:##"), "700": entity(text), "999": entity()}
            )
        )

    for _ in range(2):
        aresponses.add("example.com", "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(kind, circuit), session=session)
        first = await read(client, kind, circuit)
        second = await read(client, kind, circuit)
    assert first.kind == kind
    assert first.circuit == circuit
    assert first.day("monday").schedule.slots[0].start == time(6)
    assert second.day("monday").schedule.slots[0].start == time(9)
    assert first.day("tuesday").status == "empty"
    assert first.day("wednesday").reason_code == "missing"
    assert not first.complete
    assert first.retry_required
    assert requests == [("/JQ", QUERY), ("/JQ", QUERY)]


@pytest.mark.parametrize("value", [None, "", "---", "None"])
async def test_read_inactive_is_not_empty(
    aresponses: ResponsesMockServer, value
) -> None:
    """An inactive entity must not be writable as a cleared day."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(text=json.dumps({"700": entity(value)})),
    )
    async with aiohttp.ClientSession() as session:
        result = await BSBLAN(config(), session=session).heating_schedule()
    day = result.day("monday")
    assert day.status == "unavailable"
    assert day.reason_code == "inactive"
    assert day.schedule is None
    assert day.raw_value == value


@pytest.mark.parametrize("code", [7, 261, 256, 42])
async def test_read_device_errors_keep_context(
    aresponses: ResponsesMockServer, code: int
) -> None:
    """Device failures remain seven explicit outcomes, not a negative cache."""
    response = {param: entity("5", error=code, data_type=1) for param in IDS}
    aresponses.add(
        "example.com", "/JQ", "POST", aresponses.Response(text=json.dumps(response))
    )
    async with aiohttp.ClientSession() as session:
        result = await BSBLAN(config(), session=session).heating_schedule()
    assert not result.complete
    assert result.retry_required is (code != 7)
    assert len(result.days) == 7
    assert all(day.error_code == code and day.raw_value == "5" for day in result.days)


@pytest.mark.parametrize(
    "text",
    ["06:00-24:00", "22:00-06:00", "06:00-06:00", "06:00-08:00 07:00-09:00", "bad"],
)
async def test_read_unparsed_preserves_other_days(
    aresponses: ResponsesMockServer, text: str
) -> None:
    """Unsupported intervals retain raw text without discarding the week."""
    response = {param: entity() for param in IDS}
    response["700.1"] = entity(text)
    aresponses.add(
        "example.com", "/JQ", "POST", aresponses.Response(text=json.dumps(response))
    )
    async with aiohttp.ClientSession() as session:
        result = await BSBLAN(config(), session=session).heating_schedule()
    assert result.day("monday").status == "readable"
    assert result.day("tuesday").status == "unparsed"
    assert result.day("tuesday").raw_value == text
    assert result.day("tuesday").schedule is None
    assert not result.complete
    assert not result.retry_required


@pytest.mark.parametrize("response", [{}, {"999": entity()}])
async def test_read_missing_days_can_recover(
    aresponses: ResponsesMockServer, response
) -> None:
    """Absent IDs are requested again rather than cached as unsupported."""
    aresponses.add(
        "example.com", "/JQ", "POST", aresponses.Response(text=json.dumps(response))
    )
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(text=json.dumps({p: entity("##:##-##:##") for p in IDS})),
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        missing = await client.heating_schedule()
        recovered = await client.heating_schedule()
    assert all(day.reason_code == "missing" for day in missing.days)
    assert recovered.complete
    assert all(day.status == "empty" for day in recovered.days)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {"value": "06:00-08:00", "error": 0},
        entity(3),
        entity("06:00-08:00", data_type=0),
    ],
)
async def test_read_malformed_entities_are_contextual(
    aresponses: ResponsesMockServer, bad
) -> None:
    """Corrupt metadata stays distinct from a supported entity's unparsed text."""
    aresponses.add(
        "example.com", "/JQ", "POST", aresponses.Response(text=json.dumps({"700": bad}))
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(
            BSBLANMalformedResponseError, match=r"heating.*1.*monday.*700"
        ) as exc:
            await BSBLAN(config(), session=session).heating_schedule()
    assert exc.value.__cause__ is not None


@pytest.mark.parametrize("body", ["{bad", "[]", "null", "false", '"payload"'])
async def test_read_malformed_envelopes_keep_context(
    aresponses: ResponsesMockServer, body: str
) -> None:
    """The real transport boundary preserves decoding context and cause."""
    aresponses.add("example.com", "/JQ", "POST", aresponses.Response(text=body))
    async with aiohttp.ClientSession() as session:
        with pytest.raises(
            BSBLANMalformedResponseError, match=r"heating.*1.*700"
        ) as exc:
            await BSBLAN(config(), session=session).heating_schedule()
    if body == "{bad":
        assert isinstance(exc.value.__cause__, json.JSONDecodeError)
        assert exc.value.__cause__.doc == body


@pytest.mark.parametrize("circuit", [True, 1.0, 0, 3, None])
async def test_read_invalid_circuit_fails_before_io(circuit) -> None:
    """Even bool and numeric lookalikes cannot silently select a circuit."""
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BSBLANInvalidParameterError):
            await BSBLAN(config(), session=session).heating_schedule(circuit=circuit)


async def test_read_without_mapping_fails_before_io() -> None:
    """Unknown schedule profiles cannot fall back to fixed integer IDs."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.invalid"), session=session)
        with pytest.raises(BSBLANScheduleMappingError, match="mapping_unknown"):
            await client.hot_water_schedule()


async def test_read_config_revalidates_unchecked_mapping() -> None:
    """Unchecked pydantic construction cannot bypass local ID validation."""
    values = mapping().model_dump()
    values["monday"] = "700!4"
    invalid = ScheduleMappings.model_construct(
        heating_1=ScheduleMapping.model_construct(**values)
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ValidationError):
            BSBLAN(
                BSBLANConfig(host="example.invalid", schedule_mappings=invalid),
                session=session,
            )


async def test_read_config_is_captured_per_client(
    aresponses: ResponsesMockServer,
) -> None:
    """Changing a configuration object never silently retargets an existing client."""
    seen = []

    async def handler(request: Any) -> Any:
        seen.append(request.query["Parameter"])
        return aresponses.Response(text="{}")

    aresponses.add("example.com", "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        original = config()
        client = BSBLAN(original, session=session)
        original.schedule_mappings = ScheduleMappings()
        await client.heating_schedule()
    assert seen == [QUERY]


async def test_read_custom_request_contract_and_programming_errors() -> None:
    """Custom request implementations cannot return a non-object or hide bugs."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        client._request = AsyncMock(return_value=[])
        with pytest.raises(BSBLANMalformedResponseError, match="700"):
            await client.heating_schedule()
        client._request = AsyncMock(side_effect=RuntimeError("synthetic bug"))
        with pytest.raises(RuntimeError, match="synthetic bug"):
            await client.heating_schedule()


async def test_read_known_pps_is_not_probed() -> None:
    """Configured BSB/LPB IDs never enable schedule probing on known PPS."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        client._device = Device.model_construct(bus="PPS")
        with pytest.raises(BSBLANUnsupportedFeatureError, match="PPS"):
            await client.heating_schedule()


async def write(
    client: BSBLAN, kind: str, circuit: int | None, update: ScheduleUpdate
) -> None:
    """Exercise the two mapped public writers."""
    if kind == "hot_water":
        await client.set_hot_water_schedule(update)
    else:
        await client.set_heating_schedule(update, circuit=circuit)


@pytest.mark.parametrize(
    ("kind", "circuit"), [("hot_water", None), ("heating", 1), ("heating", 2)]
)
async def test_write_uses_the_read_mapping(
    aresponses: ResponsesMockServer, kind, circuit
) -> None:
    """A decimal-profile Tuesday is never silently written to integer 502/562."""
    seen = []

    async def handler(request: Any) -> Any:
        payload = await request.json()
        seen.append((request.path, payload))
        return aresponses.Response(
            text=json.dumps({payload["Parameter"]: {"status": 1}})
        )

    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(text=json.dumps({"700.1": entity()})),
    )
    aresponses.add("example.com", "/JS", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(kind, circuit), session=session)
        observed = await read(client, kind, circuit)
        await write(
            client,
            kind,
            circuit,
            ScheduleUpdate(tuesday=observed.day("tuesday").schedule),
        )
    assert seen == [
        ("/JS", {"Parameter": "700.1", "Value": "06:00-08:00", "Type": "1"})
    ]


async def test_write_is_sequential_in_weekday_order(
    aresponses: ResponsesMockServer,
) -> None:
    """Only populated days are written, one /JS request per day."""
    seen = []

    async def handler(request: Any) -> Any:
        payload = await request.json()
        seen.append(payload["Parameter"])
        return aresponses.Response(
            text=json.dumps({payload["Parameter"]: {"status": 1}})
        )

    aresponses.add("example.com", "/JS", "POST", handler, repeat=2)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        day = DaySchedule.from_bsblan_format("06:00-08:00")
        await client.set_heating_schedule(ScheduleUpdate(friday=day, monday=day))
    assert seen == ["700", "700.4"]


@pytest.mark.parametrize(
    ("response", "outcome"),
    [
        ({"700": {"status": 0}}, "rejected"),
        ({"700": {"status": 2}}, "rejected"),
        ({"700": {"status": True}}, "unknown"),
        ({"700": {"status": "1"}}, "unknown"),
        ({"status": "ok"}, "unknown"),
        ({}, "unknown"),
        ([], "unknown"),
        ({"700": None}, "unknown"),
        ({"999": {"status": 1}}, "unknown"),
    ],
)
async def test_write_checks_exact_integer_acknowledgement(
    aresponses: ResponsesMockServer, response, outcome
) -> None:
    """HTTP success and generic response text do not prove device acceptance."""
    seen = []

    async def handler(request: Any) -> Any:
        seen.append(await request.json())
        return aresponses.Response(text=json.dumps(response))

    aresponses.add("example.com", "/JS", "POST", handler)
    async with aiohttp.ClientSession() as session:
        day = DaySchedule.from_bsblan_format("06:00-08:00")
        with pytest.raises(BSBLANScheduleWriteError) as exc:
            await BSBLAN(config(), session=session).set_heating_schedule(
                ScheduleUpdate(monday=day, tuesday=day)
            )
    assert exc.value.acknowledged_days == ()
    assert exc.value.failed_day == "monday"
    assert exc.value.parameter_id == "700"
    assert exc.value.unattempted_days == ("tuesday",)
    assert exc.value.outcome == outcome
    assert len(seen) == 1


async def test_write_partial_rejection_preserves_progress(
    aresponses: ResponsesMockServer,
) -> None:
    """A rejected second day does not roll back Monday or send Wednesday."""
    seen = []

    async def handler(request: Any) -> Any:
        payload = await request.json()
        seen.append(payload["Parameter"])
        return aresponses.Response(
            text=json.dumps(
                {payload["Parameter"]: {"status": 1 if len(seen) == 1 else 0}}
            )
        )

    aresponses.add("example.com", "/JS", "POST", handler, repeat=2)
    async with aiohttp.ClientSession() as session:
        day = DaySchedule.from_bsblan_format("06:00-08:00")
        with pytest.raises(BSBLANScheduleWriteError) as exc:
            await BSBLAN(config(), session=session).set_heating_schedule(
                ScheduleUpdate(monday=day, tuesday=day, wednesday=day)
            )
    assert seen == ["700", "700.1"]
    assert exc.value.kind == "heating"
    assert exc.value.circuit == 1
    assert exc.value.acknowledged_days == ("monday",)
    assert exc.value.failed_day == "tuesday"
    assert exc.value.unattempted_days == ("wednesday",)
    assert exc.value.outcome == "rejected"


async def test_write_lost_response_reports_uncertain_failed_day() -> None:
    """A timed-out request may have applied; retain the cause and stop the week."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        error = BSBLANConnectionError("synthetic timeout")
        client._request = AsyncMock(side_effect=[{"700": {"status": 1}}, error])
        day = DaySchedule.from_bsblan_format("06:00-08:00")
        with pytest.raises(BSBLANScheduleWriteError) as exc:
            await client.set_heating_schedule(
                ScheduleUpdate(monday=day, tuesday=day, wednesday=day)
            )
    assert exc.value.__cause__ is error
    assert exc.value.outcome == "unknown"
    assert exc.value.acknowledged_days == ("monday",)
    assert exc.value.failed_day == "tuesday"
    assert exc.value.unattempted_days == ("wednesday",)


@pytest.mark.parametrize(
    "bad", [None, "06:00-08:00", ScheduleSnapshot.model_construct(), ScheduleUpdate()]
)
async def test_write_rejects_non_updates_and_noop_before_io(bad) -> None:
    """Snapshots/raw values/empty updates cannot initiate writes."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        client._request = AsyncMock()
        with pytest.raises(BSBLANInvalidParameterError):
            await client.set_heating_schedule(bad)
        client._request.assert_not_awaited()


@pytest.mark.parametrize("bad_later_day", ["raw", DaySchedule()])
async def test_write_invalid_later_day_prevents_earlier_writes(bad_later_day) -> None:
    """Whole-update validation happens before the first potentially partial write."""
    day = DaySchedule.from_bsblan_format("06:00-08:00")
    update = ScheduleUpdate(monday=day, tuesday=day)
    object.__setattr__(update, "tuesday", bad_later_day)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        client._request = AsyncMock()
        with pytest.raises(
            (BSBLANInvalidParameterError, BSBLANUnsupportedFeatureError)
        ):
            await client.set_heating_schedule(update)
        client._request.assert_not_awaited()


@pytest.mark.parametrize("kind", ["heating", "hot_water"])
@pytest.mark.parametrize("bus", ["BSB", "LPB", "PPS"])
async def test_write_rejects_known_read_only_bus(kind: str, bus: str) -> None:
    """Read-only metadata is enforced independently of UI restrictions."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(
            config(kind, None if kind == "hot_water" else 1), session=session
        )
        client._device = Device.model_construct(bus=bus, buswritable=0)
        client._request = AsyncMock()
        with pytest.raises(BSBLANUnsupportedFeatureError):
            await write(
                client,
                kind,
                1,
                ScheduleUpdate(monday=DaySchedule.from_bsblan_format("06:00-08:00")),
            )
        client._request.assert_not_awaited()


async def test_write_missing_mapping_cannot_use_legacy_defaults() -> None:
    """A writer never falls back to the fixed integer schedule tables."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.invalid"), session=session)
        with pytest.raises(BSBLANScheduleMappingError):
            await client.set_hot_water_schedule(
                ScheduleUpdate(monday=DaySchedule.from_bsblan_format("06:00-08:00"))
            )


@pytest.mark.parametrize("operation", ["read", "write"])
@pytest.mark.parametrize(
    ("field", "value"),
    [("host", "other.invalid"), ("port", 8081), ("passkey", "new-passkey")],
)
async def test_schedule_mapping_cannot_follow_a_changed_endpoint(
    operation: str, field: str, value
) -> None:
    """Mutable connection options must not transfer a confirmed mapping."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        client._request = AsyncMock(
            return_value={} if operation == "read" else {"700": {"status": 1}}
        )
        setattr(client.config, field, value)
        request = (
            client.heating_schedule()
            if operation == "read"
            else client.set_heating_schedule(
                ScheduleUpdate(monday=DaySchedule.from_bsblan_format("06:00-08:00"))
            )
        )
        with pytest.raises(BSBLANScheduleMappingError, match="target_changed"):
            await request
        client._request.assert_not_awaited()


async def test_target_change_between_writes_retains_partial_progress() -> None:
    """Reconfiguration during a week cannot send later days to another endpoint."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        seen = []

        async def handler(**kwargs: Any) -> Any:
            param = kwargs["data"]["Parameter"]
            seen.append(param)
            client.config.host = "other.invalid"
            return {param: {"status": 1}}

        client._request = handler
        day = DaySchedule.from_bsblan_format("06:00-08:00")
        with pytest.raises(BSBLANScheduleWriteError) as exc:
            await client.set_heating_schedule(
                ScheduleUpdate(monday=day, tuesday=day, wednesday=day)
            )
    assert seen == ["700"]
    assert exc.value.acknowledged_days == ("monday",)
    assert exc.value.failed_day == "tuesday"
    assert exc.value.unattempted_days == ("wednesday",)
    assert isinstance(exc.value.__cause__, BSBLANScheduleMappingError)
    assert exc.value.__cause__.reason == "target_changed"


async def test_write_cancellation_stops_without_wrapping() -> None:
    """Cancellation stays cancellation, not a rejected or retryable week."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(config(), session=session)
        client._request = AsyncMock(side_effect=asyncio.CancelledError)
        with pytest.raises(asyncio.CancelledError):
            await client.set_heating_schedule(
                ScheduleUpdate(monday=DaySchedule.from_bsblan_format("06:00-08:00"))
            )
