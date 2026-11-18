"""Best-effort reversible control demonstrations, never automatic transactions.

Do not run alongside other writers. Disconnects, repeated interrupts or process
termination can prevent restoration; always check the reported readback results.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bsblan import (
    BSBLANError,
    DaySchedule,
    ScheduleMappings,
    ScheduleUpdate,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from bsblan import (
        BSBLAN,
        EntityInfo,
        EntityValue,
        ScheduleSnapshot,
        StaticState,
        Weekday,
    )
    from bsblan.schedule_profiles import ScheduleKind


@dataclass(frozen=True)
class ControlOptions:
    """Validated example options; merely constructing these never performs I/O."""

    write: bool = False
    circuit: int = 1
    temperature: float = 18.0
    hvac_mode: int = 3
    mappings: ScheduleMappings = field(default_factory=ScheduleMappings)
    weekday: Weekday = "monday"
    schedule: DaySchedule | None = None
    schedule_kind: ScheduleKind | None = None


async def read_schedule(
    client: BSBLAN, options: ControlOptions
) -> ScheduleSnapshot | None:
    """Read only the explicitly configured schedule group, with no fallback scan."""
    if options.mappings.hot_water is not None:
        return await client.hot_water_schedule()
    if options.circuit in options.mappings.heating:
        return await client.heating_schedule(circuit=options.circuit)
    if not options.mappings.heating:
        if options.schedule_kind == "heating":
            return await client.heating_schedule(circuit=options.circuit)
        if options.schedule_kind == "hot_water":
            return await client.hot_water_schedule()
    return None


def _writable_value[T: EntityValue](
    attribute: EntityInfo[T] | None, label: str, *, require_permission: bool = False
) -> T:
    """Require a readable original and honor its individual permission flags."""
    if (
        attribute is None
        or attribute.value is None
        or attribute.error
        or attribute.read_write_permission is False
        or (require_permission and attribute.read_write_permission is not True)
    ):
        msg = (
            f"Cannot safely restore {label}: need an available read/write value "
            "(readwrite=0), with no device error"
        )
        raise BSBLANError(msg)
    return attribute.value


async def _read_day(
    client: BSBLAN, options: ControlOptions, *, require_permission: bool = False
) -> DaySchedule:
    """Reject original days whose parsed nonempty value cannot be written back."""
    snapshot = await read_schedule(client, options)
    if snapshot is None:
        msg = "A confirmed mapping for the selected schedule group is required"
        raise BSBLANError(msg)
    day = snapshot.day(options.weekday)
    if day.status != "readable" or day.schedule is None:
        msg = f"Cannot safely restore {options.weekday}: schedule is {day.status}"
        raise BSBLANError(msg)
    _writable_value(
        day.metadata,
        f"{options.weekday} schedule",
        require_permission=require_permission,
    )
    day.schedule.to_bsblan_format()
    return day.schedule


def _check_temperature_bounds(
    bounds: StaticState, original: float, temporary: float
) -> None:
    """Check both temperatures against available heating bounds, never cooling."""

    def first_value(*attributes: EntityInfo[float] | None) -> float | None:
        return next(
            (
                attribute.value
                for attribute in attributes
                if attribute is not None
                and not attribute.error
                and attribute.value is not None
                and math.isfinite(attribute.value)
            ),
            None,
        )

    lower = first_value(bounds.heating_protective_setpoint, bounds.min_temp)
    upper = first_value(bounds.comfort_setpoint_max, bounds.max_temp)
    if lower is None or upper is None:
        print("Heating bounds incomplete; device-side acceptance cannot be guaranteed")
    if any(
        (lower is not None and value < lower) or (upper is not None and value > upper)
        for value in (original, temporary)
    ):
        msg = f"Original and temporary temperatures must be within {lower}..{upper}"
        raise BSBLANError(msg)


async def _round_trip[T](
    label: str,
    original: T,
    temporary: T,
    write: Callable[[T], Awaitable[None]],
    read: Callable[[], Awaitable[T]],
) -> None:
    """Restore even an uncertain write, verifying changes and recovery separately."""
    if original == temporary:
        print(f"{label}: unchanged; no write needed")
        return

    async def verify(expected: T) -> None:
        actual = await read()
        if actual != expected:
            msg = (
                f"{label} readback mismatch: expected {expected!r}, received {actual!r}"
            )
            raise BSBLANError(msg)

    failure: BaseException | None = None
    try:
        print(f"Temporarily setting {label}: {temporary!r} (saved {original!r})")
        await write(temporary)
        await verify(temporary)
    except BaseException as err:
        failure = err
        raise
    finally:
        try:
            print(f"Restoring {label}: {original!r}")
            await write(original)
            await verify(original)
            print(f"Restored and verified {label}")
        except BaseException as err:
            print(
                f"RESTORATION FAILED for {label}; original value: {original!r}. "
                f"Check the controller and restore manually: {err}",
                file=sys.stderr,
            )
            if failure is not None:
                msg = f"{label}: operation and restoration both failed"
                raise BaseExceptionGroup(msg, [failure, err]) from None
            raise


async def run_roundtrip(client: BSBLAN, options: ControlOptions) -> None:
    """Save all originals, then exercise and restore one setting at a time."""
    if not options.write:
        msg = "Control changes require explicit --write opt-in"
        raise BSBLANError(msg)
    if not math.isfinite(options.temperature):
        msg = "Temporary temperature must be finite"
        raise BSBLANError(msg)
    has_mapping = (
        bool(options.mappings.heating) or options.mappings.hot_water is not None
    )
    has_selection = has_mapping or options.schedule_kind is not None
    if has_selection != (options.schedule is not None):
        msg = "A schedule write requires a selected group or mapping and a target"
        raise BSBLANError(msg)
    if options.schedule is not None:
        options.schedule.to_bsblan_format()
    device = client.device_info or await client.device()
    if device.bus not in {"BSB", "LPB", "PPS"}:
        msg = "Control writes require an explicit supported bus type"
        raise BSBLANError(msg)
    if device.is_pps_bus and not device.is_bus_writable:
        msg = "PPS gateway write access is disabled"
        raise BSBLANError(msg)
    # On BSB/LPB, disabled defaults do not override an individual readwrite=0.
    require_permission = not device.is_bus_writable
    state = await client.state(
        include=["target_temperature", "hvac_mode"], circuit=options.circuit
    )
    original_temperature = _writable_value(
        state.target_temperature, "temperature", require_permission=require_permission
    )
    original_mode = _writable_value(
        state.hvac_mode, "HVAC mode", require_permission=require_permission
    )
    if not math.isfinite(original_temperature):
        msg = "Original temperature must be finite to restore it"
        raise BSBLANError(msg)
    valid_modes = (0, 1, 3) if device.is_pps_bus else (0, 1, 2, 3)
    if original_mode not in valid_modes or options.hvac_mode not in valid_modes:
        msg = "Original and temporary HVAC modes must both be writable on this bus"
        raise BSBLANError(msg)
    bounds = await client.static_values(circuit=options.circuit)
    _check_temperature_bounds(bounds, original_temperature, options.temperature)
    original_day = (
        await _read_day(client, options, require_permission=require_permission)
        if has_selection
        else None
    )
    print(
        f"Saved temperature: {original_temperature}; saved HVAC mode: {original_mode}"
    )
    if original_day is not None:
        print(f"Saved {options.weekday} schedule: {original_day.to_bsblan_format()}")

    async def write_temperature(value: float) -> None:
        await client.thermostat(target_temperature=str(value), circuit=options.circuit)

    async def read_temperature() -> float:
        state = await client.state(
            include=["target_temperature"], circuit=options.circuit
        )
        return _writable_value(
            state.target_temperature,
            "temperature readback",
            require_permission=require_permission,
        )

    async def write_mode(value: int) -> None:
        await client.thermostat(hvac_mode=value, circuit=options.circuit)

    async def read_mode() -> int:
        state = await client.state(include=["hvac_mode"], circuit=options.circuit)
        return _writable_value(
            state.hvac_mode, "HVAC mode readback", require_permission=require_permission
        )

    await _round_trip(
        "temperature",
        original_temperature,
        options.temperature,
        write_temperature,
        read_temperature,
    )
    await _round_trip(
        "HVAC mode", original_mode, options.hvac_mode, write_mode, read_mode
    )
    if original_day is not None and options.schedule is not None:

        async def write_day(value: DaySchedule) -> None:
            update = ScheduleUpdate(**{options.weekday: value})
            if options.mappings.hot_water is not None or (
                not options.mappings.heating and options.schedule_kind == "hot_water"
            ):
                await client.set_hot_water_schedule(update)
            else:
                await client.set_heating_schedule(update, circuit=options.circuit)

        async def read_day() -> DaySchedule:
            return await _read_day(
                client, options, require_permission=require_permission
            )

        await _round_trip(
            f"{options.weekday} schedule",
            original_day,
            options.schedule,
            write_day,
            read_day,
        )
