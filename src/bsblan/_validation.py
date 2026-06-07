"""Lazy section/group validation for the BSBLAN client.

Owns the on-demand validation of API sections and hot water parameter groups,
including the per-key locks that serialize concurrent first-time validation,
the set of already-validated hot water groups, and the hot water parameter
cache. The owning client keeps thin ``_ensure_*`` / ``set_hot_water_cache``
facades that delegate here.

The validator reads the shared API config and performs requests through
callables supplied by the owning client so it does not hold a back-reference to
the facade. The temperature-unit extraction hooks are likewise injected.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, cast

from .constants import PPS_HEATING_PARAMS, PPS_STATIC_VALUES_PARAMS, ErrorMsg
from .exceptions import BSBLANError
from .utility import APIValidator

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

    from .bsblan import SectionLiteral
    from .constants import APIConfig

logger = logging.getLogger(__name__)


class SectionValidator:
    """Validate API sections and hot water groups on demand.

    The validator owns the lazy-loading state (per-section/group locks, the
    validated-group set, and the hot water parameter cache) and the wrapped
    :class:`APIValidator`. Shared API config is read through ``get_api_data``
    and device requests go through ``request`` so the validator never holds a
    back-reference to the owning client.
    """

    def __init__(
        self,
        *,
        request: Callable[..., Awaitable[dict[str, Any]]],
        extract_params_summary: Callable[[dict[Any, Any]], dict[Any, Any]],
        get_api_data: Callable[[], APIConfig | None],
        should_extract_temperature_unit: Callable[
            [SectionLiteral, list[str] | None, dict[str, Any]], bool
        ],
        extract_temperature_unit: Callable[[dict[str, Any]], None],
    ) -> None:
        """Initialize the validator with the client's collaborators.

        Args:
            request: Callable performing a device request, returning the JSON
                response.
            extract_params_summary: Callable building the request summary
                (``string_par`` + value list) from a parameter map.
            get_api_data: Callable returning the current shared API config.
            should_extract_temperature_unit: Predicate deciding whether a
                validation response should update the temperature unit.
            extract_temperature_unit: Callable updating the temperature unit
                from a validation response.

        """
        self._request = request
        self._extract_params_summary = extract_params_summary
        self._get_api_data = get_api_data
        self._should_extract_temperature_unit = should_extract_temperature_unit
        self._extract_temperature_unit = extract_temperature_unit

        self._api_validator: APIValidator | None = None
        # Cache of validated hot water parameter id -> name.
        self._hot_water_param_cache: dict[str, str] = {}
        # Track which hot water param groups have been validated.
        self._validated_hot_water_groups: set[str] = set()
        # Locks to prevent concurrent validation of the same section/group.
        self._section_locks: dict[str, asyncio.Lock] = {}
        self._hot_water_group_locks: dict[str, asyncio.Lock] = {}

    @property
    def hot_water_param_cache(self) -> dict[str, str]:
        """Return the cache of validated hot water parameters."""
        return self._hot_water_param_cache

    def get_section_params(self, section: SectionLiteral) -> dict[str, str]:
        """Return the validated parameter map for a section.

        Args:
            section: The section to read parameters for.

        Returns:
            dict[str, str]: Mapping of parameter id to parameter name.

        """
        return cast("APIValidator", self._api_validator).get_section_params(section)

    def apply_bus_specific_api_config(
        self, api_data: APIConfig | None, *, uses_pps_bus: bool
    ) -> None:
        """Apply bus-specific parameter maps to the current API config.

        Args:
            api_data: The shared API config to mutate in place.
            uses_pps_bus: Whether the device uses the PPS bus.

        """
        if api_data is None or not uses_pps_bus:
            return

        api_data["heating"] = PPS_HEATING_PARAMS.copy()
        api_data["staticValues"] = PPS_STATIC_VALUES_PARAMS.copy()
        api_data["heating_circuit2"] = {}
        api_data["staticValues_circuit2"] = {}

    def setup(self, api_data: APIConfig, *, uses_pps_bus: bool) -> None:
        """Create the API validator without validating sections.

        This applies any bus-specific configuration and builds the validator
        infrastructure but defers actual section validation until the data is
        needed (lazy loading).

        Args:
            api_data: The shared API config to validate against.
            uses_pps_bus: Whether the device uses the PPS bus.

        """
        self.apply_bus_specific_api_config(api_data, uses_pps_bus=uses_pps_bus)
        self._api_validator = APIValidator(api_data)

    async def _run_once_locked(
        self,
        key: str,
        locks: dict[str, asyncio.Lock],
        is_done: Callable[[], bool],
        body: Callable[[], Awaitable[None]],
    ) -> None:
        """Run an idempotent async operation at most once per key.

        Implements double-checked locking: a fast path when the work is already
        done, a per-key lock to serialize concurrent first-time callers, and a
        re-check after acquiring the lock so only one caller runs ``body``.

        Args:
            key (str): Identifier for the one-time operation.
            locks (dict[str, asyncio.Lock]): Registry of per-key locks, created
                on demand.
            is_done (Callable[[], bool]): Predicate returning True when the work
                is already complete.
            body (Callable[[], Awaitable[None]]): Coroutine factory executed once
                while holding the lock.

        """
        if is_done():
            return

        if key not in locks:
            locks[key] = asyncio.Lock()

        async with locks[key]:
            if is_done():
                return
            await body()

    async def ensure_section_validated(
        self, section: SectionLiteral, include: list[str] | None = None
    ) -> None:
        """Ensure a section is validated before use (lazy loading).

        This method validates a section on-demand when it's first accessed.
        Subsequent calls for the same section are no-ops.

        Uses a per-section lock to prevent concurrent validation of the same
        section, which could cause duplicate network requests.

        Args:
            section: The section name to validate
            include: Optional list of parameter names to validate. If None,
                validates all parameters for the section.

        Raises:
            BSBLANError: If the API validator is not initialized.

        """
        if not self._api_validator:
            raise BSBLANError(ErrorMsg.API_VALIDATOR_NOT_INITIALIZED)

        api_validator = self._api_validator

        async def _validate() -> None:
            logger.debug("Lazy loading section: %s", section)
            response_data = await self._validate_api_section(section, include)

            if response_data and self._should_extract_temperature_unit(
                section, include, response_data
            ):
                self._extract_temperature_unit(response_data)

        await self._run_once_locked(
            section,
            self._section_locks,
            lambda: api_validator.is_section_validated(section),
            _validate,
        )

    async def ensure_hot_water_group_validated(
        self,
        group_name: str,
        param_filter: set[str],
        include: list[str] | None = None,
    ) -> None:
        """Validate only a specific hot water parameter group (lazy loading).

        This enables more granular lazy loading for hot water - instead of
        validating all 29 hot water parameters at once, we only validate
        the specific group needed (essential: 5, config: 16, schedule: 8).

        Uses a per-group lock to prevent concurrent validation of the same
        group, which could cause duplicate network requests.

        Args:
            group_name: Name of the group (essential, config, schedule)
            param_filter: Set of parameter IDs for this group
            include: Optional list of parameter names to include in validation.
                If provided, only these parameters will be validated.

        """

        async def _validate() -> None:
            if not self._api_validator:
                raise BSBLANError(ErrorMsg.API_VALIDATOR_NOT_INITIALIZED)

            api_data = self._get_api_data()
            if not api_data:
                raise BSBLANError(ErrorMsg.API_DATA_NOT_INITIALIZED)

            logger.debug("Lazy loading hot water group: %s", group_name)

            # Get the base hot water params from API config
            section_data = api_data.get("hot_water", {})

            # Filter to only the params in this group
            group_params = {
                param_id: param_name
                for param_id, param_name in section_data.items()
                if param_id in param_filter
            }

            # Apply include filter if specified - only validate requested params
            if include is not None:
                group_params = {
                    param_id: name
                    for param_id, name in group_params.items()
                    if name in include
                }

            if not group_params:
                logger.debug("No parameters to validate for group %s", group_name)
                self._validated_hot_water_groups.add(group_name)
                return

            # Request only these specific parameters from the device
            params = self._extract_params_summary(group_params)
            response_data = await self._request(
                params={"Parameter": params["string_par"]}
            )

            # Validate and filter out unsupported params
            params_to_remove = []
            for param_id, param_name in group_params.items():
                if param_id not in response_data:
                    logger.info(
                        "Hot water param %s (%s) not found in response",
                        param_id,
                        param_name,
                    )
                    params_to_remove.append(param_id)
                    continue

                param_data = response_data[param_id]
                if not param_data or param_data.get("value") in (None, "---"):
                    logger.info(
                        "Hot water param %s (%s) returned invalid value: %s",
                        param_id,
                        param_name,
                        param_data.get("value") if param_data else None,
                    )
                    params_to_remove.append(param_id)

            # Update the cache with validated params for this group
            for param_id, param_name in group_params.items():
                if param_id not in params_to_remove:
                    self._hot_water_param_cache[param_id] = param_name

            # Mark this group as validated
            self._validated_hot_water_groups.add(group_name)
            logger.debug(
                "Validated hot water group '%s': %d params, removed %d unsupported",
                group_name,
                len(group_params),
                len(params_to_remove),
            )

        await self._run_once_locked(
            group_name,
            self._hot_water_group_locks,
            lambda: group_name in self._validated_hot_water_groups,
            _validate,
        )

    async def _validate_api_section(
        self, section: SectionLiteral, include: list[str] | None = None
    ) -> dict[str, Any] | None:
        """Validate a specific section of the API configuration.

        Args:
            section: The section name to validate
            include: Optional list of parameter names to validate. If None,
                validates all parameters for the section.

        Returns:
            dict[str, Any] | None: The response data from the device, or None if
                section was already validated or validation failed

        Raises:
            BSBLANError: If the API validator or API data is not initialized,
                or the section is not found.

        """
        if not self._api_validator:
            raise BSBLANError(ErrorMsg.API_VALIDATOR_NOT_INITIALIZED)

        api_data = self._get_api_data()
        if not api_data:
            raise BSBLANError(ErrorMsg.API_DATA_NOT_INITIALIZED)

        # Assign to local variable after asserting it's not None
        api_validator = self._api_validator

        if api_validator.is_section_validated(section):
            return None

        # Get parameters for the section
        try:
            section_data = api_data[section]
        except KeyError as err:
            msg = ErrorMsg.SECTION_NOT_FOUND.format(section)
            raise BSBLANError(msg) from err

        # Filter to only included params if specified
        if include is not None:
            section_data = {
                param_id: name
                for param_id, name in section_data.items()
                if name in include
            }

        try:
            # Request data from device for validation
            params = self._extract_params_summary(section_data)
            response_data = await self._request(
                params={"Parameter": params["string_par"]}
            )

            # Validate the section against actual device response
            api_validator.validate_section(section, response_data, include)
            # Update API data with validated configuration
            api_data[section] = api_validator.get_section_params(section)

            # Cache hot water parameters if this is the hot_water section
            if section == "hot_water":
                self.populate_hot_water_cache()
        except BSBLANError as err:
            logger.warning("Failed to validate section %s: %s", section, str(err))
            # Reset validation state for this section
            api_validator.reset_validation(section)
            raise
        else:
            return response_data

    def populate_hot_water_cache(self) -> None:
        """Populate the hot water parameter cache with all available parameters."""
        if not self._api_validator:
            return

        # Get all hot water parameters and cache them
        hotwater_params = self._api_validator.get_section_params("hot_water")
        self._hot_water_param_cache = hotwater_params.copy()
        logger.debug("Cached %d hot water parameters", len(self._hot_water_param_cache))

    def set_hot_water_cache(self, params: dict[str, str]) -> None:
        """Set the hot water parameter cache manually (for testing).

        Args:
            params: Dictionary of parameter_id -> parameter_name mappings

        """
        self._hot_water_param_cache = params.copy()
        logger.debug("Manually set cache with %d hot water parameters", len(params))
