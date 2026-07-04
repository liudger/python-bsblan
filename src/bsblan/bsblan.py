"""Asynchronous Python client for BSB-Lan."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

import aiohttp
from aiohttp.hdrs import METH_POST

from ._hot_water import HotWaterManager
from ._parameters import ParameterReader
from ._schedules import ScheduleManager
from ._temperature import TemperatureManager
from ._thermostat import ThermostatWriter
from ._transport import BSBLANTransport
from ._validation import SectionValidator
from ._version import VersionResolver
from .constants import (
    API_BASIC,
    API_FULL,
    APIConfig,
    CircuitConfig,
    ErrorMsg,
    Validation,
)
from .exceptions import (
    BSBLANConnectionError,
    BSBLANError,
    BSBLANInvalidParameterError,
)
from .models import (
    ApiVersion,
    Device,
    DeviceTime,
    DHWSchedule,
    EntityInfo,
    HeatingSchedule,
    HeatingTimeSwitchPrograms,
    HotWaterConfig,
    HotWaterSchedule,
    HotWaterState,
    Info,
    Sensor,
    SetHotWaterParam,
    State,
    StaticState,
)
from .utility import is_param_value_active, validate_time_format

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
    "staticValues_circuit2",
]

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
    _json_api_version: str | None = None
    _supports_full_config: bool | None = None
    _api_data: APIConfig | None = None
    _device: Device | None = None
    _initialized: bool = False
    _available_circuits: set[int] | None = None
    _transport: BSBLANTransport = field(init=False)
    _version_resolver: VersionResolver = field(init=False)
    _temperature: TemperatureManager = field(init=False)
    _validator: SectionValidator = field(init=False)
    _parameters: ParameterReader = field(init=False)
    _hot_water: HotWaterManager = field(init=False)
    _schedules: ScheduleManager = field(init=False)
    _thermostat_writer: ThermostatWriter = field(init=False)

    def __post_init__(self) -> None:
        """Wire up internal collaborators after dataclass construction."""
        self._transport = BSBLANTransport(
            self.config,
            lambda: self.session,
            lambda: self._firmware_version,
        )
        self._version_resolver = VersionResolver()
        self._temperature = TemperatureManager(
            static_values=lambda **kw: self.static_values(**kw),  # noqa: PLW0108
            get_available_circuits=lambda: self._available_circuits,
        )
        # _request and _extract_params_summary are monkeypatched by some tests,
        # so resolve them lazily instead of binding them at construction time.
        self._validator = SectionValidator(
            request=lambda **kw: self._request(**kw),  # noqa: PLW0108
            extract_params_summary=(
                lambda d: self._extract_params_summary(d)  # noqa: PLW0108
            ),
            get_api_data=lambda: self._api_data,
            should_extract_temperature_unit=self._should_extract_temperature_unit,
            extract_temperature_unit=self._extract_temperature_unit_from_response,
        )
        self._parameters = ParameterReader(
            request=lambda **kw: self._request(**kw),  # noqa: PLW0108
            get_api_data=lambda: self._api_data,
        )
        self._hot_water = HotWaterManager(
            ensure_group_validated=self._ensure_hot_water_group_validated,
            get_param_cache=lambda: self._validator.hot_water_param_cache,
            apply_include_filter=self._apply_include_filter,
            request_named_params=self._request_named_params,
            validate_single_parameter=self._validate_single_parameter,
            set_payload=self._set_payload,
            set_device_state=self._set_device_state,
        )
        self._schedules = ScheduleManager(
            request=lambda **kw: self._request(**kw),  # noqa: PLW0108
            extract_params_summary=(
                lambda d: self._extract_params_summary(d)  # noqa: PLW0108
            ),
            apply_include_filter=self._apply_include_filter,
            validate_circuit=self._validate_circuit,
            set_payload=self._set_payload,
            set_device_state=self._set_device_state,
        )
        self._thermostat_writer = ThermostatWriter(
            uses_pps_bus=lambda: self._uses_pps_bus,
            temperature=self._temperature,
            set_payload=self._set_payload,
        )

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

        Uses the configured operating mode probe parameters from
        CircuitConfig.PROBE_PARAMS as the only discovery signal. Status
        parameters are not queried during discovery to keep setup lightweight
        and avoid excluding valid circuits when status data is unavailable.

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
        if self._supports_full_config is False:
            logger.debug(
                "Basic single-circuit configuration detected; skipping circuit "
                "discovery and assuming only circuit 1 is available"
            )
            self._available_circuits = {1}
            return [1]
        if self._uses_pps_bus:
            return await self._get_available_pps_circuits()

        available: list[int] = []
        for circuit, param_id in CircuitConfig.PROBE_PARAMS.items():
            try:
                response = await self._request(
                    params={"Parameter": param_id},
                )
            except BSBLANError:
                logger.debug(
                    "Circuit %d not available (operating mode request failed)",
                    circuit,
                )
                continue

            # A circuit exists if the response contains the operating mode key
            # with an active value (not an empty dict, and not None/"---").
            param_data = response.get(param_id)
            if not is_param_value_active(param_data):
                logger.debug(
                    "Circuit %d has no operating mode data (not supported)",
                    circuit,
                )
                continue

            available.append(circuit)
        self._available_circuits = set(available)
        return sorted(available)

    async def _get_available_pps_circuits(self) -> list[int]:
        """Detect the single PPS room-unit climate circuit."""
        param_id = "15000"
        try:
            response = await self._request(params={"Parameter": param_id})
        except BSBLANError:
            logger.debug("PPS climate circuit not available")
            self._available_circuits = set()
            return []

        if not is_param_value_active(response.get(param_id)):
            logger.debug("PPS climate circuit has no active operating mode value")
            self._available_circuits = set()
            return []
        self._available_circuits = {1}
        return [1]

    async def _setup_api_validator(self) -> None:
        """Set up the API validator without validating sections.

        This creates the validator infrastructure but defers actual
        section validation until the data is needed (lazy loading).
        """
        if self._supports_full_config is None:
            raise BSBLANError(ErrorMsg.CONFIG_NOT_RESOLVED)

        # Initialize API data if not already done
        if self._api_data is None:
            self._api_data = self._copy_api_config()

        # Build the validator (applies bus-specific config, defers validation)
        self._validator.setup(self._api_data, uses_pps_bus=self._uses_pps_bus)

    def _apply_bus_specific_api_config(self) -> None:
        """Apply bus-specific parameter maps to the current API config."""
        self._validator.apply_bus_specific_api_config(
            self._api_data, uses_pps_bus=self._uses_pps_bus
        )

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
        await self._validator.ensure_section_validated(section, include)

    def _should_extract_temperature_unit(
        self,
        section: SectionLiteral,
        include: list[str] | None,
        response_data: dict[str, Any],
    ) -> bool:
        """Return whether the validation response should update temperature unit."""
        return self._temperature.should_extract_temperature_unit(
            section, include, response_data
        )

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
        await self._validator.ensure_hot_water_group_validated(
            group_name, param_filter, include
        )

    def _populate_hot_water_cache(self) -> None:
        """Populate the hot water parameter cache with all available parameters."""
        self._validator.populate_hot_water_cache()

    def _extract_temperature_unit_from_response(
        self, response_data: dict[str, Any]
    ) -> None:
        """Extract temperature unit from heating section response data.

        Gets the unit from the target_temperature parameter, which is always
        present in the heating section.

        Args:
            response_data: The response data from heating section validation

        """
        self._temperature.extract_temperature_unit_from_response(response_data)

    def set_hot_water_cache(self, params: dict[str, str]) -> None:
        """Set the hot water parameter cache manually (for testing).

        Args:
            params: Dictionary of parameter_id -> parameter_name mappings

        """
        self._validator.set_hot_water_cache(params)

    async def _fetch_firmware_version(self) -> None:
        """Fetch the firmware version if not already available."""
        if self._firmware_version is None:
            device = await self.device()
            self._firmware_version = device.version
            logger.debug("BSBLAN version: %s", self._firmware_version)
            await self._fetch_json_api_version()
            self._resolve_api_capabilities()

    async def _fetch_json_api_version(self) -> None:
        """Fetch the BSB-LAN JSON-API version from the /JV endpoint.

        The JSON-API version (e.g. ``"2.0"``) is the documented,
        firmware-independent compatibility signal and the sole input for
        selecting the configuration. Older firmware may not expose the /JV
        endpoint; in that case the value is left as ``None`` and
        :meth:`_resolve_api_capabilities` raises ``BSBLANVersionError``.
        """
        if self._json_api_version is not None:
            return
        try:
            response = await self._request(base_path="/JV")
            api_version = ApiVersion.model_validate(response)
        except (BSBLANError, ValueError, KeyError) as exc:
            # /JV is unavailable or returned an unexpected payload; leave the
            # JSON-API version unset so capability resolution can reject it.
            logger.debug("JSON-API version unavailable from /JV: %s", exc)
            return
        self._json_api_version = api_version.api_version
        logger.debug("BSBLAN JSON-API version: %s", self._json_api_version)

    @property
    def device_info(self) -> Device | None:
        """Return cached device metadata from the last /JI response."""
        return self._device

    @property
    def json_api_version(self) -> str | None:
        """Return the BSB-LAN JSON-API version reported by ``/JV``.

        This is the firmware-independent JSON-API version (e.g. ``"2.0"``) and
        the signal used to select the device configuration. Returns ``None``
        until ``/JV`` has been queried during initialization.
        """
        return self._json_api_version

    @property
    def supports_time_sync(self) -> bool:
        """Return cached support for the normal BSB/LPB time sync command."""
        return self._device is not None and self._device.supports_time_sync

    @property
    def _uses_pps_bus(self) -> bool:
        """Return whether cached metadata identifies the device as PPS."""
        return self._device is not None and self._device.is_pps_bus

    @property
    def _is_bus_writable(self) -> bool:
        """Return whether cached metadata says writes are allowed."""
        return self._device is None or self._device.is_bus_writable

    async def _ensure_device_metadata(self) -> None:
        """Fetch device metadata if it has not been loaded yet."""
        if self._device is None:
            await self.device()

    def _resolve_api_capabilities(self) -> None:
        """Resolve the API capabilities used to select the configuration.

        The BSB-LAN JSON-API version (from /JV) is the documented,
        firmware-independent compatibility signal and is the sole input for
        selecting the API configuration. The adapter firmware version (from
        /JI) is retrieved for informational purposes only and is not checked.

        Raises:
            BSBLANVersionError: If the JSON-API version is unavailable or the
                reported version is not supported.

        """
        self._supports_full_config = self._version_resolver.supports_full_config(
            json_api_version=self._json_api_version,
        )

    async def _initialize_temperature_range(
        self,
        circuit: int = 1,
    ) -> None:
        """Initialize the temperature range from static values (lazy loaded).

        This method is called on-demand when temperature range is needed.
        It uses lazy loading through static_values() which will validate
        the staticValues section if not already done.

        Args:
            circuit: The heating circuit number (1 or 2).

        Note: Temperature unit is extracted during heating section validation,
        so no extra API call is needed here.

        """
        await self._temperature.initialize_temperature_range(circuit)

    def _validate_circuit(self, circuit: int) -> None:
        """Validate the circuit number.

        Args:
            circuit: The heating circuit number to validate.

        Raises:
            BSBLANInvalidParameterError: If the circuit number is invalid.

        """
        if circuit not in CircuitConfig.VALID or (self._uses_pps_bus and circuit != 1):
            msg = ErrorMsg.INVALID_CIRCUIT.format(circuit)
            raise BSBLANInvalidParameterError(msg)

    def _validate_bus_write_supported(self) -> None:
        """Validate that cached metadata permits writes."""
        if not self._is_bus_writable:
            raise BSBLANError(ErrorMsg.BUS_WRITE_NOT_SUPPORTED)

    def _validate_time_sync_supported(self) -> None:
        """Validate that normal parameter 0 time sync is safe."""
        if not self.supports_time_sync:
            raise BSBLANError(ErrorMsg.TIME_SYNC_NOT_SUPPORTED)

    @property
    def get_temperature_unit(self) -> str:
        """Get the unit of temperature.

        Returns:
            str: The unit of temperature (°C or °F).

        Note:
            This property assumes the client has been initialized. If accessed before
            initialization, it will return the default unit (°C).

        """
        return self._temperature.unit

    def _copy_api_config(self) -> APIConfig:
        """Create a copy of the API configuration for the current capability.

        Returns:
            APIConfig: A deep copy of the API configuration.

        Raises:
            BSBLANError: If the API capability has not been resolved.

        """
        if self._supports_full_config is None:
            raise BSBLANError(ErrorMsg.CONFIG_NOT_RESOLVED)
        source_config: APIConfig = API_FULL if self._supports_full_config else API_BASIC
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
            return await self._transport.request_with_retry(
                method, base_path, data, params
            )
        except TimeoutError as e:
            raise BSBLANConnectionError(BSBLANConnectionError.message_timeout) from e
        except aiohttp.ClientError as e:
            raise BSBLANConnectionError(BSBLANConnectionError.message_error) from e

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

    def _extract_params_summary(self, params: dict[Any, Any]) -> dict[Any, Any]:
        """Get the parameters info from BSBLAN device.

        Args:
            params (dict[Any, Any]): The parameters to get info for.

        Returns:
            dict[Any, Any]: The parameters info from the BSBLAN device.

        """
        string_params = ",".join(map(str, params))
        return {"string_par": string_params, "list": list(params.values())}

    def _apply_include_filter(
        self, params: dict[str, str], include: list[str] | None
    ) -> dict[str, str]:
        """Filter a parameter map down to the requested parameter names.

        Args:
            params (dict[str, str]): Mapping of parameter ID to parameter name.
            include (list[str] | None): Parameter names to keep. If None, the
                mapping is returned unchanged.

        Returns:
            dict[str, str]: The filtered mapping (unchanged when include is None).

        Raises:
            BSBLANError: If include is an empty list, or if none of the requested
                names match the available parameters.

        """
        if include is None:
            return params
        if not include:
            raise BSBLANError(ErrorMsg.EMPTY_INCLUDE_LIST)
        include_set = set(include)
        filtered = {
            param_id: name for param_id, name in params.items() if name in include_set
        }
        if not filtered:
            raise BSBLANError(ErrorMsg.INVALID_INCLUDE_PARAMS)
        return filtered

    async def _request_named_params(self, params: dict[str, str]) -> dict[str, Any]:
        """Request parameters and key the response by parameter name.

        Args:
            params (dict[str, str]): Mapping of parameter ID to parameter name.

        Returns:
            dict[str, Any]: The device response re-keyed from parameter ID to
                parameter name, positionally matching the request order.

        """
        summary = self._extract_params_summary(params)
        data = await self._request(params={"Parameter": summary["string_par"]})
        return dict(zip(summary["list"], list(data.values()), strict=True))

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

        section_params = self._validator.get_section_params(section)

        # Guard: if validation removed all params, the section is not available
        if not section_params:
            msg = ErrorMsg.EMPTY_SECTION_PARAMS.format(section)
            raise BSBLANError(msg)

        # Filter to requested parameter names (if an include list was given)
        section_params = self._apply_include_filter(section_params, include)

        data = await self._request_named_params(section_params)
        if section == "heating" and self._uses_pps_bus:
            self._normalize_pps_state_data(data)
        return model_class.model_validate(data)

    def _normalize_pps_state_data(self, data: dict[str, Any]) -> None:
        """Normalize PPS climate values to the library's State model."""
        hvac_mode = data.get("hvac_mode")
        if not isinstance(hvac_mode, dict):
            return

        try:
            raw_mode = int(hvac_mode["value"])
        except (KeyError, TypeError, ValueError):
            return

        hvac_mode["value"] = Validation.PPS_HVAC_MODE_FROM_BSBLAN.get(
            raw_mode,
            raw_mode,
        )

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
                room1_temp_setpoint_boost.
            circuit: The heating circuit number (1 or 2). Defaults to 1.
                Circuit 2 uses separate parameter IDs but returns the
                same State model with the same field names.

        Returns:
            State: The current state of the BSBLAN device.

        Note:
            For BSB/LPB devices, hvac_mode.value is returned as a raw integer:
            0=off, 1=auto, 2=eco, 3=heat. PPS devices normalize their raw
            operating modes to the same library values, but do not support eco.

        Example:
            # Fetch only hvac_mode and current_temperature
            state = await client.state(include=["hvac_mode", "current_temperature"])

            # Fetch state for heating circuit 2
            state_hc2 = await client.state(circuit=2)

        """
        self._validate_circuit(circuit)
        section: SectionLiteral = cast(
            "SectionLiteral", CircuitConfig.HEATING_SECTIONS[circuit]
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
            circuit: The heating circuit number (1 or 2). Defaults to 1.

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
            "SectionLiteral", CircuitConfig.STATIC_SECTIONS[circuit]
        )
        return await self._fetch_section_data(section, StaticState, include)

    async def device(self) -> Device:
        """Get BSBLAN device info.

        Returns:
            Device: The BSBLAN device information.

        """
        device_info = await self._request(base_path="/JI")
        self._device = Device.model_validate(device_info)
        return self._device

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
        await self._ensure_device_metadata()
        self._validate_time_sync_supported()

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
        await self._ensure_device_metadata()
        self._validate_time_sync_supported()
        self._validate_time_format(time_value)
        response = await self._request(
            base_path="/JS", data=self._set_payload("0", time_value)
        )
        logger.debug("Response for setting time: %s", response)

    async def thermostat(  # pylint: disable=too-many-arguments
        self,
        target_temperature: str | None = None,
        hvac_mode: int | None = None,
        circuit: int = 1,
        target_temperature_high: str | float | None = None,
        *,
        cooling_operating_mode: int | None = None,
    ) -> None:
        """Change the state of the thermostat through BSB-Lan.

        Args:
            target_temperature (str | None): The target temperature to set.
            hvac_mode (int | None): The HVAC mode to set as raw integer value.
                For BSB/LPB, valid values are 0=off, 1=auto, 2=eco, 3=heat.
                For PPS, valid values are 0=off, 1=auto, and 3=heat/manual;
                they are translated to PPS raw values before posting.
            circuit: The heating circuit number (1 or 2). Defaults to 1.
            target_temperature_high: The cooling comfort setpoint to set.
            cooling_operating_mode: The cooling circuit operating mode to set
                as raw integer value: 0=Protection, 1=Automatic, 2=Reduced,
                3=Comfort. Not supported on PPS devices.

        Example:
            # Set HC1 temperature
            await client.thermostat(target_temperature="21.0")

            # Set HC1 cooling comfort setpoint
            await client.thermostat(target_temperature_high="24.0")

            # Set HC1 cooling operating mode
            await client.thermostat(cooling_operating_mode=1)

            # Set HC2 mode
            await client.thermostat(hvac_mode=1, circuit=2)

        """
        self._validate_circuit(circuit)
        if self._uses_pps_bus:
            self._validate_bus_write_supported()
        await self._initialize_temperature_range(circuit)

        self._validate_single_parameter(
            target_temperature,
            hvac_mode,
            target_temperature_high,
            cooling_operating_mode,
            error_msg=ErrorMsg.MULTI_PARAMETER,
        )

        state = await self._thermostat_writer.prepare_state(
            target_temperature,
            hvac_mode,
            circuit,
            target_temperature_high,
            cooling_operating_mode=cooling_operating_mode,
        )
        await self._set_device_state(state)

    async def _validate_target_temperature_high(
        self,
        target_temperature_high: str | float,
        circuit: int = 1,
    ) -> None:
        """Validate the cooling target temperature value."""
        await self._temperature.validate_target_temperature_high(
            target_temperature_high,
            circuit,
        )

    async def _validate_target_temperature(
        self,
        target_temperature: str,
        circuit: int = 1,
    ) -> None:
        """Validate the target temperature.

        This method lazy-loads the temperature range if not already initialized.
        If the device does not provide min/max temperature parameters,
        only validates that the value is a valid float.

        Args:
            target_temperature (str): The target temperature to validate.
            circuit: The heating circuit number (1 or 2).

        Raises:
            BSBLANInvalidParameterError: If the target temperature is invalid.

        """
        await self._temperature.validate_target_temperature(
            target_temperature,
            circuit,
        )

    def _validate_time_format(self, time_value: str) -> None:
        """Validate the time format.

        Args:
            time_value (str): The time value to validate.

        Raises:
            BSBLANInvalidParameterError: If the time format is invalid.

        """
        try:
            validate_time_format(time_value, Validation.MIN_YEAR, Validation.MAX_YEAR)
        except ValueError as err:
            raise BSBLANInvalidParameterError(str(err)) from err

    def _set_payload(
        self, parameter: str, value: str, type_: str = "1"
    ) -> dict[str, Any]:
        """Build a BSB-LAN ``/JS`` set-parameter payload.

        Args:
            parameter (str): The BSB-LAN parameter ID to set.
            value (str): The value to write for the parameter.
            type_ (str): The BSB-LAN set type. Defaults to ``"1"``.

        Returns:
            dict[str, Any]: The payload for a ``/JS`` set request.

        """
        return {"Parameter": parameter, "Value": value, "Type": type_}

    async def _set_device_state(self, state: dict[str, Any]) -> None:
        """Set device state via BSB-LAN API.

        This is a unified method for setting thermostat and hot water state.

        Args:
            state (dict[str, Any]): The state to set on the device.

        """
        response = await self._request(base_path="/JS", data=state)
        logger.debug("Response for setting: %s", response)

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
        return await self._hot_water.state(include)

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
        return await self._hot_water.config(include)

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
        return await self._hot_water.schedule(include)

    async def heating_schedule(
        self,
        include: list[str] | None = None,
        circuit: int = 1,
    ) -> HeatingTimeSwitchPrograms:
        """Get heating time switch programs for a specific circuit.

        Args:
            include: Optional list of day names to fetch. If None,
                fetches all schedule parameters. Valid names include:
                monday, tuesday, wednesday, thursday,
                friday, saturday, sunday, standard_values.
            circuit: The heating circuit number (1 or 2). Defaults to 1.

        Returns:
            HeatingTimeSwitchPrograms: Heating schedule information.

        """
        return await self._schedules.heating_schedule(include, circuit)

    async def set_heating_schedule(
        self,
        schedule: HeatingSchedule,
        circuit: int = 1,
    ) -> None:
        """Set heating time switch programs for a specific circuit.

        This method allows setting weekly heating schedules using a type-safe
        interface with TimeSlot and DaySchedule objects.

        Args:
            schedule: HeatingSchedule object containing the weekly schedule.
            circuit: The heating circuit number (1 or 2). Defaults to 1.

        Raises:
            BSBLANError: If no schedule is provided.

        """
        await self._schedules.set_heating_schedule(schedule, circuit)

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
        await self._hot_water.set_hot_water(params)

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
        await self._schedules.set_hot_water_schedule(schedule)

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
        return self._hot_water.prepare_state(params)

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
        return await self._parameters.read_parameters(parameter_ids)

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
        return self._parameters.get_parameter_id(parameter_name)

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
        return self._parameters.get_parameter_ids(parameter_names)

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
        return await self._parameters.read_parameters_by_name(parameter_names)
