"""Asynchronous Python client for BSB-Lan."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

import aiohttp
import backoff
from aiohttp.hdrs import METH_POST
from aiohttp.helpers import BasicAuth
from packaging import version as pkg_version
from yarl import URL

from .constants import (
    API_DATA_NOT_INITIALIZED_ERROR_MSG,
    API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG,
    API_VERSION_ERROR_MSG,
    API_VERSIONS,
    CIRCUIT_HEATING_SECTIONS,
    CIRCUIT_PROBE_PARAMS,
    CIRCUIT_STATIC_SECTIONS,
    CIRCUIT_THERMOSTAT_PARAMS,
    DHW_TIME_PROGRAM_PARAMS,
    EMPTY_INCLUDE_LIST_ERROR_MSG,
    FIRMWARE_VERSION_ERROR_MSG,
    HOT_WATER_CONFIG_PARAMS,
    HOT_WATER_ESSENTIAL_PARAMS,
    HOT_WATER_SCHEDULE_PARAMS,
    INVALID_INCLUDE_PARAMS_ERROR_MSG,
    MAX_VALID_YEAR,
    MIN_VALID_YEAR,
    MULTI_PARAMETER_ERROR_MSG,
    NO_PARAMETER_IDS_ERROR_MSG,
    NO_PARAMETER_NAMES_ERROR_MSG,
    NO_SCHEDULE_ERROR_MSG,
    NO_STATE_ERROR_MSG,
    PARAMETER_NAMES_NOT_RESOLVED_ERROR_MSG,
    SESSION_NOT_INITIALIZED_ERROR_MSG,
    SETTABLE_HOT_WATER_PARAMS,
    TEMPERATURE_RANGE_ERROR_MSG,
    VALID_CIRCUITS,
    VALID_HVAC_MODES,
    VERSION_ERROR_MSG,
    APIConfig,
)
from .exceptions import (
    BSBLANAuthError,
    BSBLANConnectionError,
    BSBLANError,
    BSBLANInvalidParameterError,
    BSBLANVersionError,
)
from .models import (
    DaySchedule,
    Device,
    DeviceTime,
    DHWSchedule,
    EntityInfo,
    HotWaterConfig,
    HotWaterSchedule,
    HotWaterState,
    Info,
    Sensor,
    SetHotWaterParam,
    State,
    StaticState,
)
from .utility import APIValidator, validate_time_format

if TYPE_CHECKING:
    from typing import Self

    from aiohttp.client import ClientSession

SectionLiteral = Literal[
    "heating",
    "staticValues",
    "device",
    "sensor",
    "hot_water",
    "heating_circuit2",
    "heating_circuit3",
    "staticValues_circuit2",
    "staticValues_circuit3",
]

# TypeVar for hot water data models
HotWaterDataT = TypeVar(
    "HotWaterDataT", HotWaterState, HotWaterConfig, HotWaterSchedule
)

# TypeVar for section data models
SectionDataT = TypeVar("SectionDataT", State, Sensor, StaticState, Info)

logger = logging.getLogger(__name__)


@dataclass
class BSBLANConfig:
    """Configuration for BSBLAN."""

    host: str
    username: str | None = None
    password: str | None = None
    passkey: str | None = None
    port: int = 80
    request_timeout: int = 10


@dataclass
class BSBLAN:
    """Main class for handling connections with BSBLAN."""

    config: BSBLANConfig
    session: ClientSession | None = None
    _close_session: bool = False
    _firmware_version: str | None = None
    _api_version: str | None = None
    _min_temp: float | None = None
    _max_temp: float | None = None
    _temperature_range_initialized: bool = False
    _api_data: APIConfig | None = None
    _initialized: bool = False
    _api_validator: APIValidator = field(init=False)
    _temperature_unit: str = "°C"
    # Per-circuit temperature ranges: circuit_number -> (min, max, initialized)
    _circuit_temp_ranges: dict[int, dict[str, float | None]] = field(
        default_factory=dict,
    )
    _circuit_temp_initialized: set[int] = field(default_factory=set)
    _hot_water_param_cache: dict[str, str] = field(default_factory=dict)
    # Track which hot water param groups have been validated
    _validated_hot_water_groups: set[str] = field(default_factory=set)
    # Locks to prevent concurrent validation of the same section/group
    _section_locks: dict[str, asyncio.Lock] = field(default_factory=dict)
    _hot_water_group_locks: dict[str, asyncio.Lock] = field(default_factory=dict)

    async def __aenter__(self) -> Self:
        """Enter the context manager.

        Returns:
            Self: The initialized BSBLAN instance.

        """
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._close_session = True
        await self.initialize()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the context manager.

        Args:
            *args: Variable length argument list.

        """
        if self._close_session and self.session:
            await self.session.close()

    async def initialize(self) -> None:
        """Initialize the BSBLAN client.

        This performs minimal initialization for fast startup.
        Section validation is deferred until actually needed (lazy loading).
        """
        if not self._initialized:
            await self._fetch_firmware_version()
            await self._setup_api_validator()
            self._initialized = True

    async def get_available_circuits(self) -> list[int]:
        """Detect which heating circuits are available on the device.

        Probes the operating mode parameter for each circuit (1, 2, 3).
        A circuit is considered available if the device returns a non-empty
        response with a valid value (not empty ``{}``).

        This is useful for integration setup flows (e.g., Home Assistant
        config flow) to discover how many circuits the user's controller
        supports.

        Returns:
            list[int]: Sorted list of available circuit numbers (e.g., [1, 2]).

        Example:
            async with BSBLAN(config) as client:
                circuits = await client.get_available_circuits()
                # circuits == [1, 2] for a dual-circuit controller

        """
        available: list[int] = []
        for circuit, param_id in CIRCUIT_PROBE_PARAMS.items():
            try:
                response = await self._request(
                    params={"Parameter": param_id},
                )
                # A circuit exists if the response contains the param_id key
                # with actual data (not an empty dict)
                if response.get(param_id):
                    available.append(circuit)
            except BSBLANError:
                logger.debug("Circuit %d not available (request failed)", circuit)
        return sorted(available)

    async def _setup_api_validator(self) -> None:
        """Set up the API validator without validating sections.

        This creates the validator infrastructure but defers actual
        section validation until the data is needed (lazy loading).
        """
        if self._api_version is None:
            raise BSBLANError(API_VERSION_ERROR_MSG)

        # Initialize API data if not already done
        if self._api_data is None:
            self._api_data = self._copy_api_config()

        # Initialize the API validator (but don't validate sections yet)
        self._api_validator = APIValidator(self._api_data)

    async def _ensure_section_validated(
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

        """
        if not self._api_validator:
            raise BSBLANError(API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG)

        # Fast path: skip if already validated (no lock needed)
        if self._api_validator.is_section_validated(section):
            return

        # Get or create lock for this section
        if section not in self._section_locks:
            self._section_locks[section] = asyncio.Lock()

        async with self._section_locks[section]:
            # Double-check after acquiring lock (another task may have validated)
            if self._api_validator.is_section_validated(section):
                return

            logger.debug("Lazy loading section: %s", section)
            response_data = await self._validate_api_section(section, include)

            # Extract temperature unit from heating section validation
            # (parameter 710 - target_temperature is always in heating section)
            if section == "heating" and response_data:
                self._extract_temperature_unit_from_response(response_data)

    async def _ensure_hot_water_group_validated(
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
        # Fast path: skip if already validated (no lock needed)
        if group_name in self._validated_hot_water_groups:
            return

        if not self._api_validator:
            raise BSBLANError(API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG)

        if not self._api_data:
            raise BSBLANError(API_DATA_NOT_INITIALIZED_ERROR_MSG)

        # Get or create lock for this group
        if group_name not in self._hot_water_group_locks:
            self._hot_water_group_locks[group_name] = asyncio.Lock()

        async with self._hot_water_group_locks[group_name]:
            # Double-check after acquiring lock (another task may have validated)
            if group_name in self._validated_hot_water_groups:
                return

            logger.debug("Lazy loading hot water group: %s", group_name)

            # Get the base hot water params from API config
            section_data = self._api_data.get("hot_water", {})

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
            params = await self._extract_params_summary(group_params)
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

    async def _initialize_api_validator(self) -> None:
        """Initialize and validate API data against device capabilities.

        DEPRECATED: This method validates all sections upfront.
        Use _setup_api_validator() + _ensure_section_validated() for lazy loading.
        This method is kept for backwards compatibility.
        """
        if self._api_version is None:
            raise BSBLANError(API_VERSION_ERROR_MSG)

        # Initialize API data if not already done
        if self._api_data is None:
            self._api_data = self._copy_api_config()

        # Initialize the API validator
        self._api_validator = APIValidator(self._api_data)

        # Perform initial validation of each section (eager loading)
        sections: list[SectionLiteral] = [
            "heating",
            "sensor",
            "staticValues",
            "device",
            "hot_water",
        ]
        for section in sections:
            response_data = await self._validate_api_section(section)

            # Extract temperature unit from heating section validation
            # (parameter 710 - target_temperature is always in heating section)
            if section == "heating" and response_data:
                self._extract_temperature_unit_from_response(response_data)

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
            BSBLANError: If the API validator is not initialized

        """
        if not self._api_validator:
            raise BSBLANError(API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG)

        if not self._api_data:
            raise BSBLANError(API_DATA_NOT_INITIALIZED_ERROR_MSG)

        # Assign to local variable after asserting it's not None
        api_validator = self._api_validator

        if api_validator.is_section_validated(section):
            return None

        # Get parameters for the section
        try:
            section_data = self._api_data[section]
        except KeyError as err:
            error_msg = f"Section '{section}' not found in API data"
            raise BSBLANError(error_msg) from err

        # Filter to only included params if specified
        if include is not None:
            section_data = {
                param_id: name
                for param_id, name in section_data.items()
                if name in include
            }

        try:
            # Request data from device for validation
            params = await self._extract_params_summary(section_data)
            response_data = await self._request(
                params={"Parameter": params["string_par"]}
            )

            # Validate the section against actual device response
            api_validator.validate_section(section, response_data, include)
            # Update API data with validated configuration
            if self._api_data:
                self._api_data[section] = api_validator.get_section_params(section)

            # Cache hot water parameters if this is the hot_water section
            if section == "hot_water":
                self._populate_hot_water_cache()
        except BSBLANError as err:
            logger.warning("Failed to validate section %s: %s", section, str(err))
            # Reset validation state for this section
            api_validator.reset_validation(section)
            raise
        else:
            return response_data

    def _populate_hot_water_cache(self) -> None:
        """Populate the hot water parameter cache with all available parameters."""
        if not self._api_validator:
            return

        # Get all hot water parameters and cache them
        hotwater_params = self._api_validator.get_section_params("hot_water")
        self._hot_water_param_cache = hotwater_params.copy()
        logger.debug("Cached %d hot water parameters", len(self._hot_water_param_cache))

    def _extract_temperature_unit_from_response(
        self, response_data: dict[str, Any]
    ) -> None:
        """Extract temperature unit from heating section response data.

        Gets the unit from parameter 710 (target_temperature) which is always
        present in the heating section.

        Args:
            response_data: The response data from heating section validation

        """
        # Look for parameter 710 (target_temperature) in the response
        for param_id, param_data in response_data.items():
            # Check if this is parameter 710 and has unit information
            if param_id == "710" and isinstance(param_data, dict):
                unit = param_data.get("unit", "")
                if unit in ("&deg;C", "°C"):
                    self._temperature_unit = "°C"
                elif unit == "°F":
                    self._temperature_unit = "°F"
                else:
                    # Keep default if unit is empty or unknown
                    logger.debug(
                        "Unknown or empty temperature unit from parameter 710: '%s'. "
                        "Using default (°C)",
                        unit,
                    )
                logger.debug("Temperature unit set to: %s", self._temperature_unit)
                return

        # If we didn't find parameter 710, log a warning
        logger.warning(
            "Could not find parameter 710 in heating section response. "
            "Using default temperature unit (°C)"
        )

    def set_hot_water_cache(self, params: dict[str, str]) -> None:
        """Set the hot water parameter cache manually (for testing).

        Args:
            params: Dictionary of parameter_id -> parameter_name mappings

        """
        self._hot_water_param_cache = params.copy()
        logger.debug("Manually set cache with %d hot water parameters", len(params))

    async def _fetch_firmware_version(self) -> None:
        """Fetch the firmware version if not already available."""
        if self._firmware_version is None:
            device = await self.device()
            self._firmware_version = device.version
            logger.debug("BSBLAN version: %s", self._firmware_version)
            self._set_api_version()

    def _set_api_version(self) -> None:
        """Set the API version based on the firmware version.

        Raises:
            BSBLANError: If the firmware version is not set.
            BSBLANVersionError: If the firmware version is not supported.

        """
        if not self._firmware_version:
            raise BSBLANError(FIRMWARE_VERSION_ERROR_MSG)

        version = pkg_version.parse(self._firmware_version)
        if version < pkg_version.parse("1.2.0"):
            self._api_version = "v1"
        elif version >= pkg_version.parse("5.0.0"):
            # BSB-LAN 5.0+ has breaking changes but uses v3-compatible API
            self._api_version = "v3"
        elif version >= pkg_version.parse("3.0.0"):
            self._api_version = "v3"
        else:
            raise BSBLANVersionError(VERSION_ERROR_MSG)

    async def _initialize_temperature_range(
        self,
        circuit: int = 1,
    ) -> None:
        """Initialize the temperature range from static values (lazy loaded).

        This method is called on-demand when temperature range is needed.
        It uses lazy loading through static_values() which will validate
        the staticValues section if not already done.

        Args:
            circuit: The heating circuit number (1, 2, or 3).

        Note: Temperature unit is extracted during heating section validation
        from the response (parameter 710), so no extra API call is needed here.

        """
        if circuit == 1 and not self._temperature_range_initialized:
            # HC1 uses legacy fields for backwards compatibility
            try:
                static_values = await self.static_values()
                if static_values.min_temp is not None:
                    self._min_temp = static_values.min_temp.value
                    logger.debug("Min temperature initialized: %s", self._min_temp)
                else:
                    logger.warning(
                        "min_temp not available from device, "
                        "temperature range will be None"
                    )

                if static_values.max_temp is not None:
                    self._max_temp = static_values.max_temp.value
                    logger.debug("Max temperature initialized: %s", self._max_temp)
                else:
                    logger.warning(
                        "max_temp not available from device, "
                        "temperature range will be None"
                    )
            except BSBLANError as err:
                logger.warning(
                    "Failed to get static values: %s. Temperature range will be None",
                    str(err),
                )

            self._temperature_range_initialized = True
        elif circuit != 1 and circuit not in self._circuit_temp_initialized:
            # HC2/HC3 use per-circuit storage
            try:
                static_values = await self.static_values(circuit=circuit)
                temp_range: dict[str, float | None] = {
                    "min": None,
                    "max": None,
                }
                if static_values.min_temp is not None:
                    temp_range["min"] = static_values.min_temp.value
                    logger.debug(
                        "Circuit %d min temp initialized: %s",
                        circuit,
                        temp_range["min"],
                    )
                if static_values.max_temp is not None:
                    temp_range["max"] = static_values.max_temp.value
                    logger.debug(
                        "Circuit %d max temp initialized: %s",
                        circuit,
                        temp_range["max"],
                    )
                self._circuit_temp_ranges[circuit] = temp_range
            except BSBLANError as err:
                logger.warning(
                    "Failed to get static values for circuit %d: %s. "
                    "Temperature range will be None",
                    circuit,
                    str(err),
                )
                self._circuit_temp_ranges[circuit] = {
                    "min": None,
                    "max": None,
                }

            self._circuit_temp_initialized.add(circuit)

    def _validate_circuit(self, circuit: int) -> None:
        """Validate the circuit number.

        Args:
            circuit: The heating circuit number to validate.

        Raises:
            BSBLANInvalidParameterError: If the circuit number is invalid.

        """
        if circuit not in VALID_CIRCUITS:
            msg = f"Invalid circuit number: {circuit}. Must be 1, 2, or 3."
            raise BSBLANInvalidParameterError(msg)

    @property
    def get_temperature_unit(self) -> str:
        """Get the unit of temperature.

        Returns:
            str: The unit of temperature (°C or °F).

        Note:
            This property assumes the client has been initialized. If accessed before
            initialization, it will return the default unit (°C).

        """
        return self._temperature_unit

    async def _initialize_api_data(self) -> APIConfig:
        """Initialize and cache the API data.

        Returns:
            APIConfig: The API configuration data.

        Raises:
            BSBLANError: If the API version or data is not initialized.

        """
        if self._api_data is None:
            self._api_data = self._copy_api_config()
            logger.debug("API data initialized for version: %s", self._api_version)
        if self._api_data is None:
            raise BSBLANError(API_DATA_NOT_INITIALIZED_ERROR_MSG)
        return self._api_data

    def _copy_api_config(self) -> APIConfig:
        """Create a copy of the API configuration for the current version.

        Returns:
            APIConfig: A deep copy of the API configuration.

        Raises:
            BSBLANError: If the API version is not set.

        """
        if self._api_version is None:
            raise BSBLANError(API_VERSION_ERROR_MSG)
        source_config: APIConfig = API_VERSIONS[self._api_version]
        return cast(
            "APIConfig",
            {
                section: cast("dict[str, str]", params).copy()
                for section, params in source_config.items()
            },
        )

    async def _request(
        self,
        method: str = METH_POST,
        base_path: str = "/JQ",
        data: dict[str, object] | None = None,
        params: Mapping[str, str | int] | str | None = None,
    ) -> dict[str, Any]:
        """Handle a request to a BSBLAN device.

        Uses exponential backoff to retry on transient connection errors.
        Will not retry on authentication errors (401, 403) or not found (404).

        Args:
            method (str): The HTTP method to use for the request.
            base_path (str): The base path for the URL.
            data (dict[str, object] | None): The data to send in the request body.
            params (Mapping[str, str | int] | str | None): The query parameters
                to include in the request.

        Returns:
            dict[str, Any]: The JSON response from the BSBLAN device.

        Raises:
            BSBLANConnectionError: If there is a connection error after retries.
            BSBLANAuthError: If authentication fails (not retried).
            BSBLANError: If there is an error with the request.

        """
        try:
            return await self._request_with_retry(method, base_path, data, params)
        except TimeoutError as e:
            raise BSBLANConnectionError(BSBLANConnectionError.message_timeout) from e
        except aiohttp.ClientError as e:
            raise BSBLANConnectionError(BSBLANConnectionError.message_error) from e

    @backoff.on_exception(
        backoff.expo,
        (TimeoutError, aiohttp.ClientError),
        max_tries=3,
        max_time=30,
        giveup=lambda e: isinstance(e, aiohttp.ClientResponseError) and e.status == 404,
        logger=logger,
    )
    async def _request_with_retry(
        self,
        method: str,
        base_path: str,
        data: dict[str, object] | None,
        params: Mapping[str, str | int] | str | None,
    ) -> dict[str, Any]:
        """Execute HTTP request with retry logic.

        This internal method handles the actual HTTP request and is decorated
        with backoff for automatic retries on transient failures.

        Args:
            method: The HTTP method to use.
            base_path: The base path for the URL.
            data: The data to send in the request body.
            params: The query parameters to include.

        Returns:
            dict[str, Any]: The JSON response from the BSBLAN device.

        """
        if self.session is None:
            raise BSBLANError(SESSION_NOT_INITIALIZED_ERROR_MSG)
        url = self._build_url(base_path)
        auth = self._get_auth()
        headers = self._get_headers()

        try:
            async with asyncio.timeout(self.config.request_timeout):
                async with self.session.request(
                    method,
                    url,
                    auth=auth,
                    params=params,
                    json=data,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    response_data = cast("dict[str, Any]", await response.json())
                    return self._process_response(response_data, base_path)
        except aiohttp.ClientResponseError as e:
            if e.status in (401, 403):
                raise BSBLANAuthError from e
            raise
        except (ValueError, UnicodeDecodeError) as e:
            # Handle JSON decode errors and other parsing issues
            error_msg = f"Invalid response format from BSB-LAN device: {e!s}"
            raise BSBLANError(error_msg) from e

    def _process_response(
        self, response_data: dict[str, Any], base_path: str
    ) -> dict[str, Any]:
        """Process response data based on firmware version.

        BSB-LAN 5.0+ includes additional 'payload' field in /JQ responses
        that needs to be handled for compatibility.

        Args:
            response_data: Raw response data from BSB-LAN
            base_path: The API endpoint that was called

        Returns:
            Processed response data compatible with existing code

        """
        # For non-JQ endpoints, return response as-is
        if base_path != "/JQ":
            return response_data

        # Check if we have a firmware version to determine processing
        if not self._firmware_version:
            return response_data

        # For BSB-LAN 5.0+, remove 'payload' field if present as it's for debugging
        version = pkg_version.parse(self._firmware_version)
        if version >= pkg_version.parse("5.0.0") and "payload" in response_data:
            # Remove payload field if present - it's added for debugging in 5.0+
            return {k: v for k, v in response_data.items() if k != "payload"}

        return response_data

    def _build_url(self, base_path: str) -> URL:
        """Build the URL for the request.

        Args:
            base_path (str): The base path for the URL.

        Returns:
            URL: The constructed URL.

        """
        if self.config.passkey:
            base_path = f"/{self.config.passkey}{base_path}"
        return URL.build(
            scheme="http",
            host=self.config.host,
            port=self.config.port,
            path=base_path,
        )

    def _get_auth(self) -> BasicAuth | None:
        """Get the authentication for the request.

        Returns:
            BasicAuth | None: The authentication object or None if no authentication
                is required.

        """
        if self.config.username and self.config.password:
            return BasicAuth(self.config.username, self.config.password)
        return None

    def _get_headers(self) -> dict[str, str]:
        """Get the headers for the request.

        Returns:
            dict[str, str]: The headers for the request.

        """
        return {
            "User-Agent": f"PythonBSBLAN/{self._firmware_version}",
            "Accept": "application/json, */*",
        }

    def _validate_single_parameter(self, *params: Any, error_msg: str) -> None:
        """Validate that exactly one parameter is provided.

        Args:
            *params: Variable length argument list of parameters to validate.
            error_msg (str): The error message to raise if validation fails.

        Raises:
            BSBLANError: If the validation fails.

        """
        if sum(param is not None for param in params) != 1:
            raise BSBLANError(error_msg)

    async def _extract_params_summary(self, params: dict[Any, Any]) -> dict[Any, Any]:
        """Get the parameters info from BSBLAN device.

        Args:
            params (dict[Any, Any]): The parameters to get info for.

        Returns:
            dict[Any, Any]: The parameters info from the BSBLAN device.

        """
        string_params = ",".join(map(str, params))
        return {"string_par": string_params, "list": list(params.values())}

    async def _fetch_section_data(
        self,
        section: SectionLiteral,
        model_class: type[SectionDataT],
        include: list[str] | None = None,
    ) -> SectionDataT:
        """Fetch data for a specific API section.

        This is a generic helper method that fetches parameters for a given
        section and returns the appropriate model. It uses lazy loading to
        validate the section on first access.

        Args:
            section: The API section name to fetch data from.
            model_class: The dataclass type to deserialize the response into.
            include: Optional list of parameter names to fetch. If None,
                fetches all parameters for the section.

        Returns:
            The populated model instance.

        Raises:
            BSBLANError: If include is specified but none of the parameters
                are valid for this section.

        """
        # Lazy load: validate section on first access (only for included params)
        await self._ensure_section_validated(section, include)

        section_params = self._api_validator.get_section_params(section)

        # Filter parameters if include list is specified
        if include is not None:
            if not include:
                raise BSBLANError(EMPTY_INCLUDE_LIST_ERROR_MSG)
            section_params = {
                param_id: name
                for param_id, name in section_params.items()
                if name in include
            }
            if not section_params:
                raise BSBLANError(INVALID_INCLUDE_PARAMS_ERROR_MSG)

        params = await self._extract_params_summary(section_params)
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return model_class.model_validate(data)

    async def state(
        self,
        include: list[str] | None = None,
        circuit: int = 1,
    ) -> State:
        """Get the current state from BSBLAN device.

        Args:
            include: Optional list of parameter names to fetch. If None,
                fetches all state parameters. Valid names include:
                hvac_mode, target_temperature, hvac_action,
                hvac_mode_changeover, current_temperature,
                room1_thermostat_mode, room1_temp_setpoint_boost.
            circuit: The heating circuit number (1, 2, or 3). Defaults to 1.
                Circuit 2 and 3 use separate parameter IDs but return the
                same State model with the same field names.

        Returns:
            State: The current state of the BSBLAN device.

        Note:
            The hvac_mode.value is returned as a raw integer from the device:
            0=off, 1=auto, 2=eco, 3=heat.

        Example:
            # Fetch only hvac_mode and current_temperature
            state = await client.state(include=["hvac_mode", "current_temperature"])

            # Fetch state for heating circuit 2
            state_hc2 = await client.state(circuit=2)

        """
        self._validate_circuit(circuit)
        section: SectionLiteral = cast(
            "SectionLiteral", CIRCUIT_HEATING_SECTIONS[circuit]
        )
        return await self._fetch_section_data(section, State, include)

    async def sensor(self, include: list[str] | None = None) -> Sensor:
        """Get the sensor information from BSBLAN device.

        Args:
            include: Optional list of parameter names to fetch. If None,
                fetches all sensor parameters. Valid names include:
                outside_temperature, current_temperature.

        Returns:
            Sensor: The sensor information from the BSBLAN device.

        Example:
            # Fetch only outside_temperature
            sensor = await client.sensor(include=["outside_temperature"])

        """
        return await self._fetch_section_data("sensor", Sensor, include)

    async def static_values(
        self,
        include: list[str] | None = None,
        circuit: int = 1,
    ) -> StaticState:
        """Get the static information from BSBLAN device.

        Args:
            include: Optional list of parameter names to fetch. If None,
                fetches all static parameters. Valid names include:
                min_temp, max_temp.
            circuit: The heating circuit number (1, 2, or 3). Defaults to 1.

        Returns:
            StaticState: The static information from the BSBLAN device.

        Example:
            # Fetch only min_temp
            static = await client.static_values(include=["min_temp"])

            # Fetch static values for heating circuit 2
            static_hc2 = await client.static_values(circuit=2)

        """
        self._validate_circuit(circuit)
        section: SectionLiteral = cast(
            "SectionLiteral", CIRCUIT_STATIC_SECTIONS[circuit]
        )
        return await self._fetch_section_data(section, StaticState, include)

    async def device(self) -> Device:
        """Get BSBLAN device info.

        Returns:
            Device: The BSBLAN device information.

        """
        device_info = await self._request(base_path="/JI")
        return Device.model_validate(device_info)

    async def info(self, include: list[str] | None = None) -> Info:
        """Get information about the current heating system config.

        Args:
            include: Optional list of parameter names to fetch. If None,
                fetches all info parameters. Valid names include:
                device_identification, controller_family, controller_variant.

        Returns:
            Info: The information about the current heating system config.

        Example:
            # Fetch only device_identification
            info = await client.info(include=["device_identification"])

        """
        return await self._fetch_section_data("device", Info, include)

    async def time(self) -> DeviceTime:
        """Get the current time from the BSB-LAN device.

        Returns:
            DeviceTime: The current time information from the BSB-LAN device.

        """
        # Get only parameter 0 for time
        data = await self._request(params={"Parameter": "0"})
        # Create the data dictionary in the expected format
        time_data = {"time": data["0"]}
        return DeviceTime.model_validate(time_data)

    async def set_time(self, time_value: str) -> None:
        """Set the time on the BSB-LAN device.

        Args:
            time_value (str): The time value to set in format "DD.MM.YYYY HH:MM:SS"
                (e.g., "13.08.2025 10:25:55").

        Raises:
            BSBLANInvalidParameterError: If the time format is invalid.

        """
        self._validate_time_format(time_value)
        state: dict[str, object] = {
            "Parameter": "0",
            "Value": time_value,
            "Type": "1",
        }
        response = await self._request(base_path="/JS", data=state)
        logger.debug("Response for setting time: %s", response)

    async def thermostat(
        self,
        target_temperature: str | None = None,
        hvac_mode: int | None = None,
        circuit: int = 1,
    ) -> None:
        """Change the state of the thermostat through BSB-Lan.

        Args:
            target_temperature (str | None): The target temperature to set.
            hvac_mode (int | None): The HVAC mode to set as raw integer value.
                Valid values: 0=off, 1=auto, 2=eco, 3=heat.
            circuit: The heating circuit number (1, 2, or 3). Defaults to 1.

        Example:
            # Set HC1 temperature
            await client.thermostat(target_temperature="21.0")

            # Set HC2 mode
            await client.thermostat(hvac_mode=1, circuit=2)

        """
        self._validate_circuit(circuit)
        await self._initialize_temperature_range(circuit)

        self._validate_single_parameter(
            target_temperature,
            hvac_mode,
            error_msg=MULTI_PARAMETER_ERROR_MSG,
        )

        state = await self._prepare_thermostat_state(
            target_temperature,
            hvac_mode,
            circuit,
        )
        await self._set_device_state(state)

    async def _prepare_thermostat_state(
        self,
        target_temperature: str | None,
        hvac_mode: int | None,
        circuit: int = 1,
    ) -> dict[str, Any]:
        """Prepare the thermostat state for setting.

        Args:
            target_temperature (str | None): The target temperature to set.
            hvac_mode (int | None): The HVAC mode to set as raw integer.
            circuit: The heating circuit number (1, 2, or 3).

        Returns:
            dict[str, Any]: The prepared state for the thermostat.

        """
        param_ids = CIRCUIT_THERMOSTAT_PARAMS[circuit]
        state: dict[str, Any] = {}
        if target_temperature is not None:
            await self._validate_target_temperature(
                target_temperature,
                circuit,
            )
            state.update(
                {
                    "Parameter": param_ids["target_temperature"],
                    "Value": target_temperature,
                    "Type": "1",
                },
            )
        if hvac_mode is not None:
            self._validate_hvac_mode(hvac_mode)
            state.update(
                {
                    "Parameter": param_ids["hvac_mode"],
                    "Value": str(hvac_mode),
                    "Type": "1",
                },
            )
        return state

    async def _validate_target_temperature(
        self,
        target_temperature: str,
        circuit: int = 1,
    ) -> None:
        """Validate the target temperature.

        This method lazy-loads the temperature range if not already initialized.

        Args:
            target_temperature (str): The target temperature to validate.
            circuit: The heating circuit number (1, 2, or 3).

        Raises:
            BSBLANError: If the temperature range cannot be initialized.
            BSBLANInvalidParameterError: If the target temperature is invalid.

        """
        if circuit == 1:
            # HC1 uses legacy fields for backwards compatibility
            if self._min_temp is None or self._max_temp is None:
                await self._initialize_temperature_range(circuit)

            if self._min_temp is None or self._max_temp is None:
                raise BSBLANError(TEMPERATURE_RANGE_ERROR_MSG)

            min_temp = self._min_temp
            max_temp = self._max_temp
        else:
            # HC2/HC3 use per-circuit storage
            if circuit not in self._circuit_temp_initialized:
                await self._initialize_temperature_range(circuit)

            temp_range = self._circuit_temp_ranges.get(circuit, {})
            min_temp = temp_range.get("min")
            max_temp = temp_range.get("max")

            if min_temp is None or max_temp is None:
                raise BSBLANError(TEMPERATURE_RANGE_ERROR_MSG)

        try:
            temp = float(target_temperature)
            if not (min_temp <= temp <= max_temp):
                raise BSBLANInvalidParameterError(target_temperature)
        except ValueError as err:
            raise BSBLANInvalidParameterError(target_temperature) from err

    def _validate_hvac_mode(self, hvac_mode: int) -> None:
        """Validate the HVAC mode.

        Args:
            hvac_mode (int): The HVAC mode to validate (0-3).

        Raises:
            BSBLANInvalidParameterError: If the HVAC mode is invalid.

        """
        if hvac_mode not in VALID_HVAC_MODES:
            raise BSBLANInvalidParameterError(str(hvac_mode))

    def _validate_time_format(self, time_value: str) -> None:
        """Validate the time format.

        Args:
            time_value (str): The time value to validate.

        Raises:
            BSBLANInvalidParameterError: If the time format is invalid.

        """
        try:
            validate_time_format(time_value, MIN_VALID_YEAR, MAX_VALID_YEAR)
        except ValueError as err:
            raise BSBLANInvalidParameterError(str(err)) from err

    async def _set_device_state(self, state: dict[str, Any]) -> None:
        """Set device state via BSB-LAN API.

        This is a unified method for setting thermostat and hot water state.

        Args:
            state (dict[str, Any]): The state to set on the device.

        """
        response = await self._request(base_path="/JS", data=state)
        logger.debug("Response for setting: %s", response)

    async def _fetch_hot_water_data(
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
        await self._ensure_hot_water_group_validated(group_name, param_filter, include)

        # Use cached validated params
        filtered_params = {
            param_id: param_name
            for param_id, param_name in self._hot_water_param_cache.items()
            if param_id in param_filter
        }

        # Apply include filter if specified
        if include is not None:
            if not include:
                raise BSBLANError(EMPTY_INCLUDE_LIST_ERROR_MSG)
            filtered_params = {
                param_id: name
                for param_id, name in filtered_params.items()
                if name in include
            }
            if not filtered_params:
                raise BSBLANError(INVALID_INCLUDE_PARAMS_ERROR_MSG)

        if not filtered_params:
            raise BSBLANError(error_msg)

        params = await self._extract_params_summary(filtered_params)
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return model_class.model_validate(data)

    async def hot_water_state(self, include: list[str] | None = None) -> HotWaterState:
        """Get essential hot water state for frequent polling.

        This method returns only the most important hot water parameters
        that are typically checked frequently for monitoring purposes.
        This reduces API calls and improves performance for regular polling.

        Uses granular lazy loading - only validates the 5 essential params,
        not all 29 hot water parameters.

        Args:
            include: Optional list of parameter names to fetch. If None,
                fetches all essential hot water parameters. Valid names include:
                operating_mode, nominal_setpoint, release,
                dhw_actual_value_top_temperature, state_dhw_pump.

        Returns:
            HotWaterState: Essential hot water state information.

        Example:
            # Fetch only operating_mode and nominal_setpoint
            state = await client.hot_water_state(
                include=["operating_mode", "nominal_setpoint"]
            )

        """
        return await self._fetch_hot_water_data(
            param_filter=HOT_WATER_ESSENTIAL_PARAMS,
            model_class=HotWaterState,
            error_msg="No essential hot water parameters available",
            group_name="essential",
            include=include,
        )

    async def hot_water_config(
        self, include: list[str] | None = None
    ) -> HotWaterConfig:
        """Get hot water configuration and advanced settings.

        This method returns configuration parameters that are typically
        set once and checked less frequently.

        Uses granular lazy loading - only validates the 16 config params.

        Args:
            include: Optional list of parameter names to fetch. If None,
                fetches all config hot water parameters. Valid names include:
                eco_mode_selection, nominal_setpoint_max, reduced_setpoint,
                dhw_charging_priority, operating_mode_changeover,
                legionella_function, legionella_function_setpoint,
                legionella_function_periodicity, legionella_function_day,
                legionella_function_time, legionella_function_dwelling_time,
                legionella_circulation_pump, legionella_circulation_temp_diff,
                dhw_circulation_pump_release, dhw_circulation_pump_cycling,
                dhw_circulation_setpoint.

        Returns:
            HotWaterConfig: Hot water configuration information.

        Example:
            # Fetch only legionella settings
            config = await client.hot_water_config(
                include=["legionella_function", "legionella_function_setpoint"]
            )

        """
        return await self._fetch_hot_water_data(
            param_filter=HOT_WATER_CONFIG_PARAMS,
            model_class=HotWaterConfig,
            error_msg="No hot water configuration parameters available",
            group_name="config",
            include=include,
        )

    async def hot_water_schedule(
        self, include: list[str] | None = None
    ) -> HotWaterSchedule:
        """Get hot water time program schedules.

        This method returns time program settings that are typically
        configured once and rarely changed.

        Uses granular lazy loading - only validates the 8 schedule params.

        Args:
            include: Optional list of parameter names to fetch. If None,
                fetches all schedule parameters. Valid names include:
                dhw_time_program_monday, dhw_time_program_tuesday,
                dhw_time_program_wednesday, dhw_time_program_thursday,
                dhw_time_program_friday, dhw_time_program_saturday,
                dhw_time_program_sunday, dhw_time_program_standard_values.

        Returns:
            HotWaterSchedule: Hot water schedule information.

        Example:
            # Fetch only Monday's schedule
            schedule = await client.hot_water_schedule(
                include=["dhw_time_program_monday"]
            )

        """
        return await self._fetch_hot_water_data(
            param_filter=HOT_WATER_SCHEDULE_PARAMS,
            model_class=HotWaterSchedule,
            error_msg="No hot water schedule parameters available",
            group_name="schedule",
            include=include,
        )

    async def set_hot_water(self, params: SetHotWaterParam) -> None:
        """Change the state of the hot water system through BSB-Lan.

        Only one parameter should be set at a time (BSB-LAN API limitation).

        Example:
            params = SetHotWaterParam(nominal_setpoint=55.0)
            await client.set_hot_water(params)

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
            error_msg=MULTI_PARAMETER_ERROR_MSG,
        )

        state = self._prepare_hot_water_state(params)
        await self._set_device_state(state)

    async def set_hot_water_schedule(self, schedule: DHWSchedule) -> None:
        """Set hot water time program schedules.

        This method allows setting weekly DHW schedules using a type-safe
        interface with TimeSlot and DaySchedule objects.

        Example:
            schedule = DHWSchedule(
                monday=DaySchedule(slots=[
                    TimeSlot(time(6, 0), time(8, 0)),
                    TimeSlot(time(17, 0), time(21, 0)),
                ]),
                tuesday=DaySchedule(slots=[
                    TimeSlot(time(6, 0), time(8, 0)),
                ])
            )
            await client.set_hot_water_schedule(schedule)

        Args:
            schedule: DHWSchedule object containing the weekly schedule.

        Raises:
            BSBLANError: If no schedule is provided.

        """
        if not schedule.has_any_schedule():
            raise BSBLANError(NO_SCHEDULE_ERROR_MSG)

        # Invert DHW_TIME_PROGRAM_PARAMS to get day_name -> param_id mapping
        # Exclude standard_values as it's not a day of the week
        day_param_map = {
            v: k for k, v in DHW_TIME_PROGRAM_PARAMS.items() if v != "standard_values"
        }

        for day_name, param_id in day_param_map.items():
            day_schedule: DaySchedule | None = getattr(schedule, day_name)
            if day_schedule is not None:
                state = {
                    "Parameter": param_id,
                    "Value": day_schedule.to_bsblan_format(),
                    "Type": "1",
                }
                await self._set_device_state(state)

    def _prepare_hot_water_state(
        self,
        params: SetHotWaterParam,
    ) -> dict[str, Any]:
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
        for param_id, attr_name in SETTABLE_HOT_WATER_PARAMS.items():
            value = getattr(params, attr_name)
            if value is not None:
                state.update({"Parameter": param_id, "Value": str(value), "Type": "1"})

        # Process time programs if provided using constants
        if params.dhw_time_programs:
            for param_id, attr_name in DHW_TIME_PROGRAM_PARAMS.items():
                value = getattr(params.dhw_time_programs, attr_name)
                if value is not None:
                    state.update({"Parameter": param_id, "Value": value, "Type": "1"})

        if not state:
            raise BSBLANError(NO_STATE_ERROR_MSG)
        return state

    # -------------------------------------------------------------------------
    # Low-level parameter access methods
    # -------------------------------------------------------------------------

    async def read_parameters(
        self,
        parameter_ids: list[str],
    ) -> dict[str, EntityInfo]:
        """Read specific parameters by their BSB-LAN parameter IDs.

        This low-level method allows fetching only the specific parameters
        needed, reducing network load compared to fetching entire dataclasses.

        Example:
            # Fetch only current temperature and HVAC action
            params = await client.read_parameters(["8740", "8000"])
            current_temp = params["8740"].value
            hvac_action = params["8000"].value

        Args:
            parameter_ids: List of BSB-LAN parameter IDs to fetch
                (e.g., ["700", "710"]).

        Returns:
            dict[str, EntityInfo]: Dictionary mapping parameter IDs to
                EntityInfo objects.

        Raises:
            BSBLANError: If no parameter IDs are provided or request fails.

        """
        if not parameter_ids:
            raise BSBLANError(NO_PARAMETER_IDS_ERROR_MSG)

        # Request the parameters from the device
        params_string = ",".join(parameter_ids)
        response_data = await self._request(params={"Parameter": params_string})

        # Convert response to EntityInfo objects
        result: dict[str, EntityInfo] = {}
        for param_id in parameter_ids:
            if param_id in response_data:
                param_data = response_data[param_id]
                if param_data and isinstance(param_data, dict):
                    result[param_id] = EntityInfo.model_validate(param_data)

        return result

    def get_parameter_id(self, parameter_name: str) -> str | None:
        """Look up the parameter ID for a given parameter name.

        This method searches through all known parameter mappings to find
        the ID for a given parameter name.

        Example:
            param_id = client.get_parameter_id("current_temperature")
            # Returns "8740"

        Args:
            parameter_name: The parameter name (e.g., "current_temperature").

        Returns:
            str | None: The parameter ID if found, None otherwise.

        """
        if not self._api_data:
            return None

        # Search through all sections for the parameter name
        for section_params in self._api_data.values():
            section_dict = cast("dict[str, str]", section_params)
            for param_id, param_name in section_dict.items():
                if param_name == parameter_name:
                    return param_id

        return None

    def get_parameter_ids(self, parameter_names: list[str]) -> dict[str, str]:
        """Look up parameter IDs for multiple parameter names.

        Example:
            ids = client.get_parameter_ids(["current_temperature", "hvac_mode"])
            # Returns {"current_temperature": "8740", "hvac_mode": "700"}

        Args:
            parameter_names: List of parameter names to look up.

        Returns:
            dict[str, str]: Dictionary mapping parameter names to their IDs.
                Only includes parameters that were found.

        """
        result: dict[str, str] = {}
        for name in parameter_names:
            param_id = self.get_parameter_id(name)
            if param_id is not None:
                result[name] = param_id
        return result

    async def read_parameters_by_name(
        self,
        parameter_names: list[str],
    ) -> dict[str, EntityInfo]:
        """Read specific parameters by their names.

        This is a convenience method that looks up parameter IDs by name
        and fetches the parameters in a single request.

        Example:
            # Fetch only current temperature and HVAC action by name
            params = await client.read_parameters_by_name([
                "current_temperature",
                "hvac_action"
            ])
            current_temp = params["current_temperature"].value

        Args:
            parameter_names: List of parameter names to fetch
                (e.g., ["current_temperature", "hvac_mode"]).

        Returns:
            dict[str, EntityInfo]: Dictionary mapping parameter names to EntityInfo
                objects. Only includes parameters that were found and had valid data.

        Raises:
            BSBLANError: If no parameter names are provided, no IDs could be resolved,
                or the client is not initialized.

        """
        if not parameter_names:
            raise BSBLANError(NO_PARAMETER_NAMES_ERROR_MSG)

        if not self._api_data:
            raise BSBLANError(API_DATA_NOT_INITIALIZED_ERROR_MSG)

        # Resolve names to IDs
        name_to_id = self.get_parameter_ids(parameter_names)

        if not name_to_id:
            unknown_params = ", ".join(parameter_names)
            msg = f"{PARAMETER_NAMES_NOT_RESOLVED_ERROR_MSG}: {unknown_params}"
            raise BSBLANError(msg)

        # Fetch parameters by ID
        param_ids = list(name_to_id.values())
        id_results = await self.read_parameters(param_ids)

        # Convert back to name-keyed dictionary
        # id_to_name maps param_id -> param_name for requested params only
        id_to_name = {v: k for k, v in name_to_id.items()}
        return {
            id_to_name[param_id]: entity_info
            for param_id, entity_info in id_results.items()
            if param_id in id_to_name
        }
