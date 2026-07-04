"""Hot water domain logic for BSB-LAN."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from .constants import ErrorMsg, HotWaterParams
from .exceptions import BSBLANError
from .models import (
    HotWaterConfig,
    HotWaterSchedule,
    HotWaterState,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .models import SetHotWaterParam

# TypeVar for hot water data models
HotWaterDataT = TypeVar(
    "HotWaterDataT", HotWaterState, HotWaterConfig, HotWaterSchedule
)


class HotWaterManager:
    """Read and write hot water state, configuration, and schedules."""

    def __init__(  # noqa: PLR0913  # pylint: disable=too-many-arguments
        self,
        *,
        ensure_group_validated: Callable[
            [str, set[str], list[str] | None], Awaitable[None]
        ],
        get_param_cache: Callable[[], dict[str, str]],
        apply_include_filter: Callable[
            [dict[str, str], list[str] | None], dict[str, str]
        ],
        request_named_params: Callable[[dict[str, str]], Awaitable[dict[str, Any]]],
        validate_single_parameter: Callable[..., None],
        set_payload: Callable[[str, str], dict[str, Any]],
        set_device_state: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Initialize the hot water manager.

        Args:
            ensure_group_validated: Validates a hot water param group lazily.
            get_param_cache: Returns the validated hot water param cache.
            apply_include_filter: Filters params by requested names.
            request_named_params: Requests params and maps them to names.
            validate_single_parameter: Ensures only one parameter is set.
            set_payload: Builds a set-parameter payload.
            set_device_state: Sends a set-parameter request to the device.

        """
        self._ensure_group_validated = ensure_group_validated
        self._get_param_cache = get_param_cache
        self._apply_include_filter = apply_include_filter
        self._request_named_params = request_named_params
        self._validate_single_parameter = validate_single_parameter
        self._set_payload = set_payload
        self._set_device_state = set_device_state

    async def fetch_data(
        self,
        param_filter: set[str],
        model_class: type[HotWaterDataT],
        error_msg: str,
        group_name: str,
        include: list[str] | None = None,
    ) -> HotWaterDataT:
        """Fetch hot water data for a specific parameter set.

        This is a generic helper method that fetches hot water parameters
        based on the provided filter and returns the appropriate model.
        It uses granular lazy loading to validate only the specific param group.

        Args:
            param_filter: Set of parameter IDs to fetch.
            model_class: The dataclass type to deserialize the response into.
            error_msg: Error message if no parameters are available.
            group_name: Name of the param group for lazy validation tracking.
            include: Optional list of parameter names to fetch. If None,
                fetches all parameters in the group.

        Returns:
            The populated model instance.

        Raises:
            BSBLANError: If no parameters are available for the filter.

        """
        # Granular lazy load: validate only this param group on first access
        # Pass include filter so we only validate requested params
        await self._ensure_group_validated(group_name, param_filter, include)

        # Use cached validated params
        filtered_params = {
            param_id: param_name
            for param_id, param_name in self._get_param_cache().items()
            if param_id in param_filter
        }

        # Apply include filter if specified
        filtered_params = self._apply_include_filter(filtered_params, include)

        if not filtered_params:
            raise BSBLANError(error_msg)

        data = await self._request_named_params(filtered_params)
        return model_class.model_validate(data)

    async def state(self, include: list[str] | None = None) -> HotWaterState:
        """Get essential hot water state for frequent polling.

        Args:
            include: Optional list of parameter names to fetch.

        Returns:
            HotWaterState: Essential hot water state information.

        """
        return await self.fetch_data(
            param_filter=HotWaterParams.ESSENTIAL,
            model_class=HotWaterState,
            error_msg="No essential hot water parameters available",
            group_name="essential",
            include=include,
        )

    async def config(self, include: list[str] | None = None) -> HotWaterConfig:
        """Get hot water configuration and advanced settings.

        Args:
            include: Optional list of parameter names to fetch.

        Returns:
            HotWaterConfig: Hot water configuration information.

        """
        return await self.fetch_data(
            param_filter=HotWaterParams.CONFIG,
            model_class=HotWaterConfig,
            error_msg="No hot water configuration parameters available",
            group_name="config",
            include=include,
        )

    async def schedule(self, include: list[str] | None = None) -> HotWaterSchedule:
        """Get hot water time program schedules.

        Args:
            include: Optional list of parameter names to fetch.

        Returns:
            HotWaterSchedule: Hot water schedule information.

        """
        return await self.fetch_data(
            param_filter=HotWaterParams.SCHEDULE,
            model_class=HotWaterSchedule,
            error_msg="No hot water schedule parameters available",
            group_name="schedule",
            include=include,
        )

    async def set_hot_water(self, params: SetHotWaterParam) -> None:
        """Change the state of the hot water system through BSB-Lan.

        Only one parameter should be set at a time (BSB-LAN API limitation).

        Args:
            params: SetHotWaterParam object containing the parameter to set.

        Raises:
            BSBLANError: If multiple parameters are set or no parameter is set.

        """
        # Validate only one parameter is being set
        time_program_params: list[str] = []
        if params.dhw_time_programs:
            programs = params.dhw_time_programs
            time_program_params.extend(
                prog
                for prog in [
                    programs.monday,
                    programs.tuesday,
                    programs.wednesday,
                    programs.thursday,
                    programs.friday,
                    programs.saturday,
                    programs.sunday,
                    programs.standard_values,
                ]
                if prog
            )

        self._validate_single_parameter(
            params.nominal_setpoint,
            params.reduced_setpoint,
            params.nominal_setpoint_max,
            params.operating_mode,
            params.eco_mode_selection,
            params.dhw_charging_priority,
            params.legionella_function_setpoint,
            params.legionella_function_periodicity,
            params.legionella_function_day,
            params.legionella_function_time,
            params.legionella_function_dwelling_time,
            params.operating_mode_changeover,
            *time_program_params,
            error_msg=ErrorMsg.MULTI_PARAMETER,
        )

        state = self.prepare_state(params)
        await self._set_device_state(state)

    def prepare_state(self, params: SetHotWaterParam) -> dict[str, Any]:
        """Prepare the hot water state for setting.

        Args:
            params: SetHotWaterParam object containing the parameter to set.

        Returns:
            dict[str, Any]: The prepared state for the hot water.

        Raises:
            BSBLANError: If no state is provided.

        """
        state: dict[str, Any] = {}

        # Process all mapped parameters using constants
        for param_id, attr_name in HotWaterParams.SETTABLE.items():
            value = getattr(params, attr_name)
            if value is not None:
                state.update(self._set_payload(param_id, str(value)))

        # Process time programs if provided using constants
        if params.dhw_time_programs:
            for param_id, attr_name in HotWaterParams.TIME_PROGRAMS.items():
                value = getattr(params.dhw_time_programs, attr_name)
                if value is not None:
                    state.update(self._set_payload(param_id, value))

        if not state:
            raise BSBLANError(ErrorMsg.NO_STATE)

        return state
