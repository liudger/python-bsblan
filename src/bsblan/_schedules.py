"""Heating and hot water schedule domain logic for BSB-LAN."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .constants import ErrorMsg, HeatingScheduleParams, HotWaterParams
from .exceptions import BSBLANError
from .models import HeatingTimeSwitchPrograms

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .models import DaySchedule, DHWSchedule, HeatingSchedule


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
            BSBLANError: If no schedule parameters are available.

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
            raise BSBLANError(ErrorMsg.NO_HEATING_SCHEDULE_PARAMS)

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
