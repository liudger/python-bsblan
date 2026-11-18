"""Exercise reversible example writes against an in-memory client, never a device."""

from __future__ import annotations

import asyncio
import importlib
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from bsblan import (
    BSBLANError,
    DaySchedule,
    Device,
    EntityInfo,
    ScheduleDay,
    ScheduleMapping,
    ScheduleMappings,
    ScheduleSnapshot,
    ScheduleUpdate,
    State,
    StaticState,
    TimeSlot,
)
from bsblan.schedules import WEEKDAYS

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
MAPPING = ScheduleMapping(**{name: str(500 + i) for i, name in enumerate(WEEKDAYS)})
ORIGINAL = DaySchedule((TimeSlot(time(6), time(8)),))
TEMPORARY = DaySchedule((TimeSlot(time(7), time(9)),))


def entity(value: Any, **changes: Any) -> dict[str, Any]:
    """Build metadata with explicit error and writable status."""
    return {
        "name": "test",
        "unit": "",
        "desc": "",
        "value": value,
        "dataType": 0,
        "error": 0,
        "readwrite": 0,
        **changes,
    }


def snapshot(
    kind: str, circuit: int | None, day: DaySchedule = ORIGINAL
) -> ScheduleSnapshot:
    """Build a complete synthetic snapshot, including the selected day's metadata."""
    raw = day.to_bsblan_format() if day.slots else "##:##-##:##"
    return ScheduleSnapshot(
        kind=kind,
        circuit=circuit,
        received_at=datetime.now(UTC),
        days=tuple(
            ScheduleDay(
                weekday=name,
                parameter_id=getattr(MAPPING, name),
                status="readable" if day.slots else "empty",
                schedule=day,
                metadata=entity(raw, dataType=9),
            )
            for name in WEEKDAYS
        ),
    )


class FakeClient:
    """Record public API calls and model state changes without HTTP or bus I/O."""

    def __init__(self) -> None:
        """Start from a non-demo temperature, mode and populated schedule."""
        self.device_info = Device(
            name="test", version="5.0.0", MAC="test", uptime=0, bus="BSB", buswritable=1
        )
        self.temperature = 21.0
        self.mode = 1
        self.day = ORIGINAL
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.state_override: State | None = None
        self.schedule_override: ScheduleSnapshot | None = None
        self.bounds = StaticState(
            heating_protective_setpoint=entity(5.0), comfort_setpoint_max=entity(30.0)
        )

    async def state(self, **kwargs: Any) -> State:
        """Return current live fake state, not a stale snapshot."""
        self.events.append(("state", kwargs))
        return self.state_override or State(
            target_temperature=entity(self.temperature),
            hvac_mode=entity(self.mode, dataType=1),
        )

    async def static_values(self, **kwargs: Any) -> StaticState:
        """Expose heating bounds without mutating state."""
        self.events.append(("static_values", kwargs))
        return self.bounds

    async def thermostat(self, **kwargs: Any) -> None:
        """Apply exactly one thermostat field per call."""
        self.events.append(("thermostat", kwargs))
        if "target_temperature" in kwargs:
            self.temperature = float(kwargs["target_temperature"])
        if "hvac_mode" in kwargs:
            self.mode = kwargs["hvac_mode"]

    async def heating_schedule(self, **kwargs: Any) -> ScheduleSnapshot:
        """Return selected heating-circuit observations."""
        self.events.append(("heating_schedule", kwargs))
        return self.schedule_override or snapshot(
            "heating", kwargs["circuit"], self.day
        )

    async def hot_water_schedule(self) -> ScheduleSnapshot:
        """Return hot-water observations."""
        self.events.append(("hot_water_schedule", {}))
        return self.schedule_override or snapshot("hot_water", None, self.day)

    async def set_heating_schedule(self, update: ScheduleUpdate, **kwargs: Any) -> None:
        """Record a single-day partial schedule command."""
        self.events.append(("set_heating_schedule", {"update": update, **kwargs}))
        self.day = update.tuesday

    async def set_hot_water_schedule(self, update: ScheduleUpdate) -> None:
        """Record a single-day DHW command."""
        self.events.append(("set_hot_water_schedule", {"update": update}))
        self.day = update.tuesday


@pytest.fixture
def example(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import the actual example helper with its normal sibling import path."""
    monkeypatch.syspath_prepend(str(EXAMPLES))
    return importlib.import_module("control_roundtrip")


@pytest.fixture
def device_client() -> Any:
    """Keep the typed production API separate from this deliberately small fake."""
    return FakeClient()


@pytest.mark.parametrize("kind", ["heating", "hot_water"])
@pytest.mark.parametrize("circuit", [1, 2])
async def test_read_before_write_verify_and_restore_every_setting(
    example: Any, device_client: Any, kind: str, circuit: int
) -> None:
    """Originals precede all writes and every thermostat operation uses the circuit."""
    mappings = (
        ScheduleMappings(heating={circuit: MAPPING})
        if kind == "heating"
        else ScheduleMappings(hot_water=MAPPING)
    )
    options = example.ControlOptions(
        write=True,
        circuit=circuit,
        mappings=mappings,
        weekday="tuesday",
        schedule=TEMPORARY,
    )
    await example.run_roundtrip(device_client, options)
    events = device_client.events
    first_write = next(i for i, (name, _) in enumerate(events) if name == "thermostat")
    assert {name for name, _ in events[:first_write]} >= {
        "state",
        "static_values",
        f"{kind}_schedule",
    }
    thermostat_writes = [kwargs for name, kwargs in events if name == "thermostat"]
    assert thermostat_writes == [
        {"target_temperature": "18.0", "circuit": circuit},
        {"target_temperature": "21.0", "circuit": circuit},
        {"hvac_mode": 3, "circuit": circuit},
        {"hvac_mode": 1, "circuit": circuit},
    ]
    schedule_writes = [
        kwargs for name, kwargs in events if name == f"set_{kind}_schedule"
    ]
    assert [entry["update"] for entry in schedule_writes] == [
        ScheduleUpdate(tuesday=TEMPORARY),
        ScheduleUpdate(tuesday=ORIGINAL),
    ]
    if kind == "heating":
        assert all(entry["circuit"] == circuit for entry in schedule_writes)
    assert device_client.temperature == 21
    assert device_client.mode == 1
    assert device_client.day == ORIGINAL
    assert sum(name == f"{kind}_schedule" for name, _ in events) == 3


@pytest.mark.parametrize("bus", ["BSB", "LPB"])
async def test_zero_default_indicator_allows_explicit_readwrite_parameters(
    example: Any,
    device_client: Any,
    bus: str,
) -> None:
    """Reproduce the reported buswritable=0 plus parameter readwrite=0 combination."""
    device_client.device_info = device_client.device_info.model_copy(
        update={"bus": bus, "buswritable": 0}
    )
    options = example.ControlOptions(
        write=True,
        mappings=ScheduleMappings(heating={1: MAPPING}),
        weekday="tuesday",
        schedule=TEMPORARY,
    )
    await example.run_roundtrip(device_client, options)
    assert device_client.temperature == 21
    assert device_client.mode == 1
    assert device_client.day == ORIGINAL
    assert any(name == "set_heating_schedule" for name, _ in device_client.events)


async def test_zero_default_indicator_does_not_invent_missing_permissions(
    example: Any,
    device_client: Any,
) -> None:
    """Default model zeros are not proof for overriding gateway defaults."""
    device_client.device_info = device_client.device_info.model_copy(
        update={"buswritable": 0}
    )
    device_client.state_override = State(
        target_temperature=EntityInfo[float](
            name="setpoint", unit="°C", desc="", value=21
        ),
        hvac_mode=EntityInfo[int](name="mode", unit="", desc="", value=1),
    )
    with pytest.raises(BSBLANError, match="readwrite=0"):
        await example.run_roundtrip(device_client, example.ControlOptions(write=True))
    assert all(name != "thermostat" for name, _ in device_client.events)


@pytest.mark.parametrize("field", ["target_temperature", "hvac_mode"])
@pytest.mark.parametrize("permission", [1, 2])
async def test_readonly_or_writeonly_state_blocks_demo_before_any_write(
    example: Any,
    device_client: Any,
    field: str,
    permission: int,
) -> None:
    """readwrite=1/2 must not be mistaken for writable originals by the example."""
    raw = {"target_temperature": entity(21), "hvac_mode": entity(1)}
    raw[field]["readwrite"] = permission
    device_client.state_override = State(**raw)
    with pytest.raises(BSBLANError):
        await example.run_roundtrip(device_client, example.ControlOptions(write=True))
    assert all(name != "thermostat" for name, _ in device_client.events)


async def test_equal_targets_are_not_written(example: Any, device_client: Any) -> None:
    """Do not send unnecessary commands if all selected targets already match."""
    options = example.ControlOptions(
        write=True,
        temperature=21,
        hvac_mode=1,
        mappings=ScheduleMappings(hot_water=MAPPING),
        weekday="tuesday",
        schedule=ORIGINAL,
    )
    await example.run_roundtrip(device_client, options)
    assert all(
        not name.startswith("set_") and name != "thermostat"
        for name, _ in device_client.events
    )


async def test_helper_requires_explicit_write_opt_in(
    example: Any, device_client: Any
) -> None:
    """Even a direct helper caller cannot accidentally bypass the read-only default."""
    with pytest.raises(BSBLANError, match="--write"):
        await example.run_roundtrip(device_client, example.ControlOptions())
    assert not device_client.events


@pytest.mark.parametrize(
    "state",
    [
        State(),
        State(target_temperature=entity(None), hvac_mode=entity(1)),
        State(target_temperature=entity(21, error=7), hvac_mode=entity(1)),
        State(target_temperature=entity(21, readonly=1), hvac_mode=entity(1)),
        State(target_temperature=entity(float("nan")), hvac_mode=entity(1)),
        State(target_temperature=entity(21), hvac_mode=entity(None)),
        State(target_temperature=entity(21), hvac_mode=entity(1, error=7)),
        State(target_temperature=entity(21), hvac_mode=entity(1, readonly=1)),
        State(target_temperature=entity(21), hvac_mode=entity(4)),
    ],
)
async def test_invalid_original_state_blocks_all_writes(
    example: Any, device_client: Any, state: State
) -> None:
    """Unreadable/readonly/nonfinite or unsupported originals are not restorable."""
    device_client.state_override = state
    with pytest.raises(BSBLANError):
        await example.run_roundtrip(device_client, example.ControlOptions(write=True))
    assert all(name != "thermostat" for name, _ in device_client.events)


@pytest.mark.parametrize("bus", [None, "unknown", "PPS-unknown"])
async def test_unknown_bus_blocks_writes(
    example: Any, device_client: Any, bus: str | None
) -> None:
    """Do not guess a writable bus type for a reversible-control demonstration."""
    device_client.device_info = device_client.device_info.model_copy(
        update={"bus": bus}
    )
    with pytest.raises(BSBLANError):
        await example.run_roundtrip(device_client, example.ControlOptions(write=True))
    assert not device_client.events


async def test_readonly_pps_bus_blocks_writes(example: Any, device_client: Any) -> None:
    """PPS retains its explicit gateway-wide write protection."""
    device_client.device_info = device_client.device_info.model_copy(
        update={"bus": "PPS", "buswritable": 0}
    )
    with pytest.raises(BSBLANError):
        await example.run_roundtrip(device_client, example.ControlOptions(write=True))
    assert not device_client.events


@pytest.mark.parametrize(("original", "requested"), [(2, 3), (1, 2)])
async def test_pps_modes_must_be_restorable(
    example: Any, device_client: Any, original: int, requested: int
) -> None:
    """Normalized PPS mode 2 is not writable and cannot be used in a roundtrip."""
    device_client.device_info = device_client.device_info.model_copy(
        update={"bus": "PPS"}
    )
    device_client.mode = original
    with pytest.raises(BSBLANError):
        await example.run_roundtrip(
            device_client, example.ControlOptions(write=True, hvac_mode=requested)
        )
    assert all(name != "thermostat" for name, _ in device_client.events)


@pytest.mark.parametrize(
    ("original", "requested"), [(40.0, 18.0), (21.0, 40.0), (21.0, float("inf"))]
)
async def test_temperature_preflight_checks_old_and_new_values(
    example: Any, device_client: Any, original: float, requested: float
) -> None:
    """Never enter a demo whose original cannot pass known heating bounds."""
    device_client.temperature = original
    with pytest.raises(BSBLANError):
        await example.run_roundtrip(
            device_client, example.ControlOptions(write=True, temperature=requested)
        )
    assert all(name != "thermostat" for name, _ in device_client.events)


@pytest.mark.parametrize("status", ["empty", "unavailable", "unparsed", "readonly"])
async def test_nonrestorable_schedule_blocks_even_thermostat_writes(
    example: Any, device_client: Any, status: str
) -> None:
    """Preflight the selected day before any reversible demonstration starts."""
    observed = snapshot(
        "hot_water", None, DaySchedule() if status == "empty" else ORIGINAL
    )
    day = observed.day("tuesday")
    if status in {"unavailable", "unparsed"}:
        day = ScheduleDay(weekday="tuesday", parameter_id="501", status=status)
    elif status == "readonly":
        day = day.model_copy(
            update={
                "metadata": EntityInfo[str](
                    **entity("06:00-08:00", dataType=9, readonly=1)
                )
            }
        )
    device_client.schedule_override = observed.model_copy(
        update={
            "days": tuple(
                day if item.weekday == "tuesday" else item for item in observed.days
            )
        }
    )
    options = example.ControlOptions(
        write=True,
        mappings=ScheduleMappings(hot_water=MAPPING),
        weekday="tuesday",
        schedule=TEMPORARY,
    )
    with pytest.raises(BSBLANError):
        await example.run_roundtrip(device_client, options)
    assert all(
        name != "thermostat" and not name.startswith("set_")
        for name, _ in device_client.events
    )


@pytest.mark.parametrize(
    "failure", [BSBLANError("uncertain write"), asyncio.CancelledError()]
)
async def test_uncertain_or_cancelled_write_still_restores_original(
    example: Any, failure: BaseException
) -> None:
    """Arm restoration before a request can mutate the device and then fail."""
    value = 21
    writes = []

    async def write(target: int) -> None:
        nonlocal value
        writes.append(target)
        value = target
        if target == 18:
            raise failure

    async def read() -> int:
        return value

    with pytest.raises(type(failure)):
        await example._round_trip("Temperature", 21, 18, write, read)
    assert value == 21
    assert writes == [18, 21]


async def test_temporary_readback_mismatch_still_restores(example: Any) -> None:
    """Acknowledgement alone is not a successful example write."""
    writes = AsyncMock()
    read = AsyncMock(side_effect=[19, 21])
    with pytest.raises(BSBLANError, match="readback"):
        await example._round_trip("Temperature", 21, 18, writes, read)
    assert [call.args[0] for call in writes.await_args_list] == [18, 21]
    assert read.await_count == 2


@pytest.mark.parametrize("primary_failure", [False, True])
async def test_failed_restoration_is_loud_and_preserves_both_errors(
    example: Any, capsys: pytest.CaptureFixture[str], *, primary_failure: bool
) -> None:
    """Do not hide either an uncertain change or an unsuccessful recovery."""
    write = AsyncMock(
        side_effect=[
            BSBLANError("apply failed") if primary_failure else None,
            BSBLANError("restore failed"),
        ]
    )
    read = AsyncMock(return_value=18)
    expected = BaseExceptionGroup if primary_failure else BSBLANError
    with pytest.raises(expected) as err:
        await example._round_trip("Temperature", 21, 18, write, read)
    output = capsys.readouterr().err
    assert "RESTORATION FAILED" in output
    assert "21" in output
    if primary_failure:
        assert isinstance(err.value, BaseExceptionGroup)
        assert [str(error) for error in err.value.exceptions] == [
            "apply failed",
            "restore failed",
        ]
    else:
        assert "restore failed" in str(err.value)


@pytest.mark.parametrize(
    "bounds",
    [
        StaticState(heating_protective_setpoint=entity(22.0)),
        StaticState(comfort_setpoint_max=entity(17.0)),
    ],
)
async def test_one_known_bound_still_blocks_unsafe_temperature_changes(
    example: Any,
    device_client: Any,
    bounds: StaticState,
) -> None:
    """An absent second bound must not allow violating the known heating bound."""
    device_client.bounds = bounds
    with pytest.raises(BSBLANError):
        await example.run_roundtrip(device_client, example.ControlOptions(write=True))
    assert all(name != "thermostat" for name, _ in device_client.events)
