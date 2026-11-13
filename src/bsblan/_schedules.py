"""Heating and hot water schedule domain logic for BSB-LAN."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ValidationError

from .constants import ErrorMsg, HeatingScheduleParams, HotWaterParams
from .exceptions import (
    BSBLANError,
    BSBLANInvalidParameterError,
    BSBLANMalformedResponseError,
    BSBLANScheduleMappingError,
    BSBLANUnsupportedFeatureError,
)
from .models import (
    MAX_TIME_SLOTS_PER_DAY,
    DataType,
    DaySchedule,
    EntityInfo,
    HeatingTimeSwitchPrograms,
    ScheduleDay,
    ScheduleReadMapping,
    ScheduleSnapshot,
    TimeSlot,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .models import DHWSchedule, HeatingSchedule


def _parse_schedule_day(param_id: str, raw: Any) -> ScheduleDay:
    """Validate and parse one present device response entity."""
    if not isinstance(raw, dict):
        msg = "entity must be an object"
        raise TypeError(msg)
    if "value" not in raw or type(raw.get("error")) is not int:
        msg = "entity must contain a value and integer error"
        raise ValueError(msg)
    value = raw["value"]
    if value is not None and not isinstance(value, str):
        msg = "schedule value must be a string or null"
        raise TypeError(msg)
    metadata_input = raw.copy()
    if raw["error"] and raw.get("dataType") != DataType.TIMEPROG:
        # Preserve the wire value in raw_value, without converting error data
        # to an incompatible numeric EntityInfo[str] value.
        metadata_input["value"] = None
    metadata = EntityInfo[str].model_validate(metadata_input)
    if metadata.error:
        return ScheduleDay(
            parameter_id=param_id,
            status="unavailable",
            raw_value=value,
            metadata=metadata,
            reason=f"device error {metadata.error}",
            reason_code="device_error",
            error_code=metadata.error,
            retry_hint=(
                "requires_reconfiguration"
                if metadata.error == 7
                else "retry_later"
                if metadata.error == 261
                else "unknown"
            ),
        )
    if value is None or value in {"", "---", "None"}:
        return ScheduleDay(
            parameter_id=param_id,
            status="unavailable",
            raw_value=value,
            metadata=metadata,
            reason="inactive value",
            reason_code="inactive",
            retry_hint="unknown",
        )
    if type(raw.get("dataType")) is not int or raw["dataType"] != DataType.TIMEPROG:
        msg = "unsupported or missing schedule data type"
        raise ValueError(msg)
    tokens = value.split()
    if not tokens or len(tokens) > MAX_TIME_SLOTS_PER_DAY:
        msg = "unsupported number of physical schedule slots"
        raise ValueError(msg)
    if any(
        slot_text != "##:##-##:##"
        and not re.fullmatch(r"[0-9]{2}:[0-9]{2}-[0-9]{2}:[0-9]{2}", slot_text)
        for slot_text in tokens
    ):
        msg = "unsupported structured schedule format"
        raise ValueError(msg)
    schedule = DaySchedule(
        slots=[TimeSlot.from_bsblan_format(s) for s in tokens if s != "##:##-##:##"]
    )
    for index, slot in enumerate(schedule.slots):
        if any(
            slot.start < other.end and other.start < slot.end
            for other in schedule.slots[index + 1 :]
        ):
            msg = "overlapping slots are unsupported in the structured representation"
            raise ValueError(msg)
    return ScheduleDay(
        parameter_id=param_id,
        status="readable" if schedule.slots else "empty",
        raw_value=value,
        metadata=metadata,
        schedule=schedule,
    )


def _schedule_day(
    param_id: str,
    name: str,
    raw: Any,
    circuit: int | None,
    kind: str,
) -> ScheduleDay:
    """Add day and circuit context to parsing errors."""
    try:
        return _parse_schedule_day(param_id, raw)
    except (ValueError, TypeError, AttributeError) as err:
        msg = f"Invalid {kind} schedule circuit {circuit} {name} parameter {param_id}"
        raise BSBLANMalformedResponseError(msg) from err


class ScheduleManager:
    """Read and write heating and hot water time switch programs."""

    def __init__(  # noqa: PLR0913  # pylint: disable=too-many-arguments
        self,
        *,
        request: Callable[..., Awaitable[dict[str, Any]]],
        extract_params_summary: Callable[[dict[Any, Any]], dict[Any, Any]],
        apply_include_filter: Callable[
            [dict[str, str], list[str] | None], dict[str, str]
        ],
        validate_circuit: Callable[[int], None],
        set_payload: Callable[[str, str], dict[str, Any]],
        set_device_state: Callable[[dict[str, Any]], Awaitable[None]],
        uses_pps_bus: Callable[[], bool],
    ) -> None:
        """Initialize the schedule manager.

        Args:
            request: Callable performing a client request.
            extract_params_summary: Builds the request parameter summary.
            apply_include_filter: Filters params by requested names.
            validate_circuit: Validates a heating circuit number.
            set_payload: Builds a set-parameter payload.
            set_device_state: Sends a set-parameter request to the device.

        """
        self._request = request
        self._extract_params_summary = extract_params_summary
        self._apply_include_filter = apply_include_filter
        self._validate_circuit = validate_circuit
        self._set_payload = set_payload
        self._set_device_state = set_device_state
        self._uses_pps_bus = uses_pps_bus

    async def structured_schedule(
        self,
        kind: Literal["hot_water", "heating"],
        circuit: int | None = None,
        *,
        mapping: ScheduleReadMapping | None = None,
    ) -> ScheduleSnapshot:
        """Query all day IDs and build a fresh, ID-mapped snapshot."""
        if kind == "heating":
            if circuit is None:
                msg = "A heating circuit is required"
                raise BSBLANError(msg)
            if type(circuit) is not int or circuit not in (1, 2):
                msg = f"circuit {circuit}"
                raise BSBLANInvalidParameterError(msg)
        if self._uses_pps_bus():
            msg = f"{kind} circuit {circuit}: PPS structured schedules unsupported"
            raise BSBLANUnsupportedFeatureError(msg)
        if mapping is None:
            raise BSBLANScheduleMappingError(kind, circuit, "mapping_unknown")
        if not isinstance(mapping, ScheduleReadMapping):
            raise BSBLANScheduleMappingError(kind, circuit, "invalid_mapping")
        try:
            days = ScheduleReadMapping.model_validate(mapping.model_dump()).model_dump()
        except ValidationError as err:
            raise BSBLANScheduleMappingError(kind, circuit, "invalid_mapping") from err
        context = (
            f"Invalid {kind} schedule circuit {circuit} "
            f"response for IDs {list(days.values())}"
        )
        try:
            response = await self._request(
                params={"Parameter": ",".join(days.values())}
            )
        except BSBLANMalformedResponseError as err:
            # Keep the original error and its decode cause, if any.
            err.message = f"{context}: {err}"
            err.args = (err.message,)
            raise
        received_at = datetime.now(UTC)
        if not isinstance(response, dict):
            raise BSBLANMalformedResponseError(context)
        results = {
            name: (
                _schedule_day(param, name, response[param], circuit, kind)
                if param in response
                else ScheduleDay(
                    parameter_id=param,
                    status="unavailable",
                    reason="missing",
                    reason_code="missing",
                    retry_hint="unknown",
                )
            )
            for name, param in days.items()
        }
        return ScheduleSnapshot(
            kind=kind,
            circuit=circuit,
            received_at=received_at,
            complete=all(day.status != "unavailable" for day in results.values()),
            days=results,
        )

    async def heating_schedule(
        self,
        include: list[str] | None = None,
        circuit: int = 1,
    ) -> HeatingTimeSwitchPrograms:
        """Get heating time switch programs for a specific circuit.

        Args:
            include: Optional list of day names to fetch.
            circuit: The heating circuit number (1 or 2). Defaults to 1.

        Returns:
            HeatingTimeSwitchPrograms: Heating schedule information.

        Raises:
            BSBLANUnsupportedFeatureError: If the device exposes no heating
                schedule parameters (a permanent condition).

        """
        self._validate_circuit(circuit)
        time_program_params = HeatingScheduleParams.TIME_PROGRAMS[circuit]

        filtered_params = self._apply_include_filter(time_program_params, include)

        params = self._extract_params_summary(filtered_params)
        data = await self._request(params={"Parameter": params["string_par"]})
        mapped_data = {
            name: data[param_id]
            for param_id, name in filtered_params.items()
            if param_id in data
        }

        if not mapped_data:
            raise BSBLANUnsupportedFeatureError(ErrorMsg.NO_HEATING_SCHEDULE_PARAMS)

        return HeatingTimeSwitchPrograms.model_validate(mapped_data)

    async def set_heating_schedule(
        self,
        schedule: HeatingSchedule,
        circuit: int = 1,
    ) -> None:
        """Set heating time switch programs for a specific circuit.

        Args:
            schedule: HeatingSchedule object containing the weekly schedule.
            circuit: The heating circuit number (1 or 2). Defaults to 1.

        Raises:
            BSBLANError: If no schedule is provided.

        """
        self._validate_circuit(circuit)
        await self._write_day_schedules(
            schedule,
            HeatingScheduleParams.TIME_PROGRAMS[circuit],
        )

    async def set_hot_water_schedule(self, schedule: DHWSchedule) -> None:
        """Set hot water time program schedules.

        Args:
            schedule: DHWSchedule object containing the weekly schedule.

        Raises:
            BSBLANError: If no schedule is provided.

        """
        await self._write_day_schedules(schedule, HotWaterParams.TIME_PROGRAMS)

    async def _write_day_schedules(
        self,
        schedule: HeatingSchedule | DHWSchedule,
        time_programs: dict[str, str],
    ) -> None:
        """Write populated day schedules using one request per day.

        Args:
            schedule: Weekly schedule object with per-day DaySchedule attrs.
            time_programs: Mapping of parameter IDs to day names.

        Raises:
            BSBLANError: If no schedule is provided.

        """
        if not schedule.has_any_schedule():
            raise BSBLANError(ErrorMsg.NO_SCHEDULE)

        # Invert the param mapping to get day_name -> param_id
        # Exclude standard_values as it's not a day of the week
        day_param_map = {
            v: k for k, v in time_programs.items() if v != "standard_values"
        }

        for day_name, param_id in day_param_map.items():
            day_schedule: DaySchedule | None = getattr(schedule, day_name)
            if day_schedule is not None:
                await self._set_device_state(
                    self._set_payload(param_id, day_schedule.to_bsblan_format()),
                )
