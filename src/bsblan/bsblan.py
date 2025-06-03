"""Asynchronous Python client for BSB-Lan."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

import aiohttp
from aiohttp.hdrs import METH_POST
from aiohttp.helpers import BasicAuth
from packaging import version as pkg_version
from yarl import URL

from .constants import (
    API_DATA_NOT_INITIALIZED_ERROR_MSG,
    API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG,
    API_VERSION_ERROR_MSG,
    API_VERSIONS,
    FIRMWARE_VERSION_ERROR_MSG,
    HVAC_MODE_DICT,
    HVAC_MODE_DICT_REVERSE,
    MULTI_PARAMETER_ERROR_MSG,
    NO_STATE_ERROR_MSG,
    SESSION_NOT_INITIALIZED_ERROR_MSG,
    TEMPERATURE_RANGE_ERROR_MSG,
    VERSION_ERROR_MSG,
    APIConfig,
)
from .exceptions import (
    BSBLANConnectionError,
    BSBLANError,
    BSBLANInvalidParameterError,
    BSBLANVersionError,
)
from .models import (
    Device,
    DHWTimeSwitchPrograms,
    HotWaterState,
    Info,
    Sensor,
    State,
    StaticState,
)
from .utility import APIValidator

if TYPE_CHECKING:
    from aiohttp.client import ClientSession
    from typing_extensions import Self

SectionLiteral = Literal["heating", "staticValues", "device", "sensor", "hot_water"]

logging.basicConfig(level=logging.DEBUG)
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
        """Initialize the BSBLAN client."""
        if not self._initialized:
            await self._fetch_firmware_version()
            await self._initialize_api_validator()
            await self._initialize_temperature_range()
            await self._initialize_api_data()
            self._initialized = True

    async def _initialize_api_validator(self) -> None:
        """Initialize and validate API data against device capabilities."""
        if self._api_version is None:
            raise BSBLANError(API_VERSION_ERROR_MSG)

        # Initialize API data if not already done
        if self._api_data is None:
            self._api_data = API_VERSIONS[self._api_version]

        # Initialize the API validator
        self._api_validator = APIValidator(self._api_data)

        # Perform initial validation of each section
        sections: list[SectionLiteral] = [
            "heating",
            "sensor",
            "staticValues",
            "device",
            "hot_water",
        ]
        for section in sections:
            await self._validate_api_section(section)

    async def _validate_api_section(self, section: SectionLiteral) -> None:
        """Validate a specific section of the API configuration.

        Args:
            section: The section name to validate

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
            return

        # Get parameters for the section
        try:
            section_data = self._api_data[section]
        except KeyError as err:
            error_msg = f"Section '{section}' not found in API data"
            raise BSBLANError(error_msg) from err

        try:
            # Request data from device for validation
            params = await self._extract_params_summary(section_data)
            response_data = await self._request(
                params={"Parameter": params["string_par"]}
            )

            # Validate the section against actual device response
            api_validator.validate_section(section, response_data)
            # Update API data with validated configuration
            if self._api_data:
                self._api_data[section] = api_validator.get_section_params(section)
        except BSBLANError as err:
            logger.warning("Failed to validate section %s: %s", section, str(err))
            # Reset validation state for this section
            api_validator.reset_validation(section)
            raise

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

    async def _initialize_temperature_range(self) -> None:
        """Initialize the temperature range from static values."""
        if not self._temperature_range_initialized:
            static_values = await self.static_values()
            self._min_temp = float(static_values.min_temp.value)
            self._max_temp = float(static_values.max_temp.value)
            self._temperature_range_initialized = True
            logger.debug(
                "Temperature range initialized: min=%f, max=%f",
                self._min_temp,
                self._max_temp,
            )
            # also set unit of temperature
            if static_values.min_temp.unit in ("&deg;C", "°C"):
                self._temperature_unit = "°C"
            else:
                self._temperature_unit = "°F"
            logger.debug("Temperature unit: %s", self._temperature_unit)

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
            if self._api_version is None:
                raise BSBLANError(API_VERSION_ERROR_MSG)
            self._api_data = API_VERSIONS[self._api_version]
            logger.debug("API data initialized for version: %s", self._api_version)
        if self._api_data is None:
            raise BSBLANError(API_DATA_NOT_INITIALIZED_ERROR_MSG)
        return self._api_data

    async def _request(
        self,
        method: str = METH_POST,
        base_path: str = "/JQ",
        data: dict[str, object] | None = None,
        params: Mapping[str, str | int] | str | None = None,
    ) -> dict[str, Any]:
        """Handle a request to a BSBLAN device.

        Args:
            method (str): The HTTP method to use for the request.
            base_path (str): The base path for the URL.
            data (dict[str, object] | None): The data to send in the request body.
            params (Mapping[str, str | int] | str | None): The query parameters
                to include in the request.

        Returns:
            dict[str, Any]: The JSON response from the BSBLAN device.

        Raises:
            BSBLANConnectionError: If there is a connection error.
            BSBLANError: If there is an error with the request.

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
        except asyncio.TimeoutError as e:
            raise BSBLANConnectionError(BSBLANConnectionError.message_timeout) from e
        except aiohttp.ClientError as e:
            raise BSBLANConnectionError(BSBLANConnectionError.message_error) from e
        except ValueError as e:
            raise BSBLANError(str(e)) from e

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

    async def state(self) -> State:
        """Get the current state from BSBLAN device.

        Returns:
            State: The current state of the BSBLAN device.

        """
        # Get validated parameters for heating section
        heating_params = self._api_validator.get_section_params("heating")
        params = await self._extract_params_summary(heating_params)
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        # we should convert this in homeassistant integration?
        data["hvac_mode"]["value"] = HVAC_MODE_DICT[int(data["hvac_mode"]["value"])]
        return State.from_dict(data)

    async def sensor(self) -> Sensor:
        """Get the sensor information from BSBLAN device.

        Returns:
            Sensor: The sensor information from the BSBLAN device.

        """
        sensor_params = self._api_validator.get_section_params("sensor")
        params = await self._extract_params_summary(sensor_params)
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return Sensor.from_dict(data)

    async def static_values(self) -> StaticState:
        """Get the static information from BSBLAN device.

        Returns:
            StaticState: The static information from the BSBLAN device.

        """
        static_params = self._api_validator.get_section_params("staticValues")
        params = await self._extract_params_summary(static_params)
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return StaticState.from_dict(data)

    async def device(self) -> Device:
        """Get BSBLAN device info.

        Returns:
            Device: The BSBLAN device information.

        """
        device_info = await self._request(base_path="/JI")
        return Device.from_dict(device_info)

    async def info(self) -> Info:
        """Get information about the current heating system config.

        Returns:
            Info: The information about the current heating system config.

        """
        api_data = await self._initialize_api_data()
        params = await self._extract_params_summary(api_data["device"])
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return Info.from_dict(data)

    async def thermostat(
        self,
        target_temperature: str | None = None,
        hvac_mode: str | None = None,
    ) -> None:
        """Change the state of the thermostat through BSB-Lan.

        Args:
            target_temperature (str | None): The target temperature to set.
            hvac_mode (str | None): The HVAC mode to set.

        """
        await self._initialize_temperature_range()

        self._validate_single_parameter(
            target_temperature,
            hvac_mode,
            error_msg=MULTI_PARAMETER_ERROR_MSG,
        )

        state = self._prepare_thermostat_state(target_temperature, hvac_mode)
        await self._set_thermostat_state(state)

    def _prepare_thermostat_state(
        self,
        target_temperature: str | None,
        hvac_mode: str | None,
    ) -> dict[str, Any]:
        """Prepare the thermostat state for setting.

        Args:
            target_temperature (str | None): The target temperature to set.
            hvac_mode (str | None): The HVAC mode to set.

        Returns:
            dict[str, Any]: The prepared state for the thermostat.

        """
        state: dict[str, Any] = {}
        if target_temperature is not None:
            self._validate_target_temperature(target_temperature)
            state.update(
                {"Parameter": "710", "Value": target_temperature, "Type": "1"},
            )
        if hvac_mode is not None:
            self._validate_hvac_mode(hvac_mode)
            state.update(
                {
                    "Parameter": "700",
                    "EnumValue": HVAC_MODE_DICT_REVERSE[hvac_mode],
                    "Type": "1",
                },
            )
        return state

    def _validate_target_temperature(self, target_temperature: str) -> None:
        """Validate the target temperature.

        Args:
            target_temperature (str): The target temperature to validate.

        Raises:
            BSBLANError: If the temperature range is not initialized.
            BSBLANInvalidParameterError: If the target temperature is invalid.

        """
        if self._min_temp is None or self._max_temp is None:
            raise BSBLANError(TEMPERATURE_RANGE_ERROR_MSG)

        try:
            temp = float(target_temperature)
            if not (self._min_temp <= temp <= self._max_temp):
                raise BSBLANInvalidParameterError(target_temperature)
        except ValueError as err:
            raise BSBLANInvalidParameterError(target_temperature) from err

    def _validate_hvac_mode(self, hvac_mode: str) -> None:
        """Validate the HVAC mode.

        Args:
            hvac_mode (str): The HVAC mode to validate.

        Raises:
            BSBLANInvalidParameterError: If the HVAC mode is invalid.

        """
        if hvac_mode not in HVAC_MODE_DICT_REVERSE:
            raise BSBLANInvalidParameterError(hvac_mode)

    async def _set_thermostat_state(self, state: dict[str, Any]) -> None:
        """Set the thermostat state.

        Args:
            state (dict[str, Any]): The state to set for the thermostat.

        """
        response = await self._request(base_path="/JS", data=state)
        logger.debug("Response for setting: %s", response)

    async def hot_water_state(self) -> HotWaterState:
        """Get the current hot water state from BSBLAN device.

        Returns:
            HotWaterState: The current hot water state.

        """
        hotwater_params = self._api_validator.get_section_params("hot_water")
        params = await self._extract_params_summary(hotwater_params)
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return HotWaterState.from_dict(data)

    async def set_hot_water(  # noqa: PLR0913
        self,
        nominal_setpoint: float | None = None,
        reduced_setpoint: float | None = None,
        operating_mode: str | None = None,
        dhw_time_programs: DHWTimeSwitchPrograms | None = None,
        eco_mode_selection: str | None = None,
        dhw_charging_priority: str | None = None,
        legionella_dwelling_time: float | None = None,
        legionella_circulation_pump: str | None = None,
        legionella_circulation_temp_diff: float | None = None,
        dhw_circulation_pump_release: str | None = None,
        dhw_circulation_pump_cycling: float | None = None,
        dhw_circulation_setpoint: float | None = None,
        operating_mode_changeover: str | None = None,
    ) -> None:  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        """Change the state of the hot water system through BSB-Lan.

        Args:
            nominal_setpoint (float | None): The nominal setpoint temperature to set.
            reduced_setpoint (float | None): The reduced setpoint temperature to set.
            operating_mode (str | None): The operating mode to set.
            dhw_time_programs (DHWTimeSwitchPrograms | None): Time switch programs.
            eco_mode_selection (str | None): Eco mode selection.
            dhw_charging_priority (str | None): DHW charging priority.
            legionella_dwelling_time (float | None): Legionella dwelling time.
            legionella_circulation_pump (str | None): Legionella circulation pump.
            legionella_circulation_temp_diff (float | None): Legionella circulation
                temperature difference.
            dhw_circulation_pump_release (str | None): DHW circulation pump release.
            dhw_circulation_pump_cycling (float | None): DHW circulation pump cycling.
            dhw_circulation_setpoint (float | None): DHW circulation setpoint.
            operating_mode_changeover (str | None): Operating mode changeover.

        """
        # Validate only one parameter is being set
        time_program_params = []
        if dhw_time_programs:
            if dhw_time_programs.monday:
                time_program_params.append(dhw_time_programs.monday)
            if dhw_time_programs.tuesday:
                time_program_params.append(dhw_time_programs.tuesday)
            if dhw_time_programs.wednesday:
                time_program_params.append(dhw_time_programs.wednesday)
            if dhw_time_programs.thursday:
                time_program_params.append(dhw_time_programs.thursday)
            if dhw_time_programs.friday:
                time_program_params.append(dhw_time_programs.friday)
            if dhw_time_programs.saturday:
                time_program_params.append(dhw_time_programs.saturday)
            if dhw_time_programs.sunday:
                time_program_params.append(dhw_time_programs.sunday)
            if dhw_time_programs.standard_values:
                time_program_params.append(dhw_time_programs.standard_values)

        self._validate_single_parameter(
            nominal_setpoint,
            reduced_setpoint,
            operating_mode,
            eco_mode_selection,
            dhw_charging_priority,
            legionella_dwelling_time,
            legionella_circulation_pump,
            legionella_circulation_temp_diff,
            dhw_circulation_pump_release,
            dhw_circulation_pump_cycling,
            dhw_circulation_setpoint,
            operating_mode_changeover,
            *time_program_params,
            error_msg=MULTI_PARAMETER_ERROR_MSG,
        )

        state = self._prepare_hot_water_state(
            nominal_setpoint,
            reduced_setpoint,
            operating_mode,
            dhw_time_programs,
            eco_mode_selection,
            dhw_charging_priority,
            legionella_dwelling_time,
            legionella_circulation_pump,
            legionella_circulation_temp_diff,
            dhw_circulation_pump_release,
            dhw_circulation_pump_cycling,
            dhw_circulation_setpoint,
            operating_mode_changeover,
        )
        await self._set_hot_water_state(state)

    def _prepare_hot_water_state(  # noqa: PLR0913, PLR0912
        self,
        nominal_setpoint: float | None,
        reduced_setpoint: float | None,
        operating_mode: str | None,
        dhw_time_programs: DHWTimeSwitchPrograms | None = None,
        eco_mode_selection: str | None = None,
        dhw_charging_priority: str | None = None,
        legionella_dwelling_time: float | None = None,
        legionella_circulation_pump: str | None = None,
        legionella_circulation_temp_diff: float | None = None,
        dhw_circulation_pump_release: str | None = None,
        dhw_circulation_pump_cycling: float | None = None,
        dhw_circulation_setpoint: float | None = None,
        operating_mode_changeover: str | None = None,
    ) -> dict[str, Any]:  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches
        """Prepare the hot water state for setting.

        Args:
            nominal_setpoint (float | None): The nominal setpoint temperature to set.
            reduced_setpoint (float | None): The reduced setpoint temperature to set.
            operating_mode (str | None): The operating mode to set.
            dhw_time_programs (DHWTimeSwitchPrograms | None): Time switch programs.
            eco_mode_selection (str | None): Eco mode selection.
            dhw_charging_priority (str | None): DHW charging priority.
            legionella_dwelling_time (float | None): Legionella dwelling time.
            legionella_circulation_pump (str | None): Legionella circulation pump.
            legionella_circulation_temp_diff (float | None): Legionella circulation
                temperature difference.
            dhw_circulation_pump_release (str | None): DHW circulation pump release.
            dhw_circulation_pump_cycling (float | None): DHW circulation pump cycling.
            dhw_circulation_setpoint (float | None): DHW circulation setpoint.
            operating_mode_changeover (str | None): Operating mode changeover.

        Returns:
            dict[str, Any]: The prepared state for the hot water.

        Raises:
            BSBLANError: If no state is provided.

        """
        state: dict[str, Any] = {}
        if nominal_setpoint is not None:
            state.update(
                {"Parameter": "1610", "Value": str(nominal_setpoint), "Type": "1"},
            )
        if reduced_setpoint is not None:
            state.update(
                {"Parameter": "1612", "Value": str(reduced_setpoint), "Type": "1"},
            )
        if operating_mode is not None:
            state.update(
                {
                    "Parameter": "1600",
                    "EnumValue": operating_mode,
                    "Type": "1",
                },
            )
        if eco_mode_selection is not None:
            state.update(
                {
                    "Parameter": "1601",
                    "EnumValue": eco_mode_selection,
                    "Type": "1",
                },
            )
        if dhw_charging_priority is not None:
            state.update(
                {
                    "Parameter": "1630",
                    "EnumValue": dhw_charging_priority,
                    "Type": "1",
                },
            )
        if legionella_dwelling_time is not None:
            state.update(
                {
                    "Parameter": "1646",
                    "Value": str(legionella_dwelling_time),
                    "Type": "1",
                },
            )
        if legionella_circulation_pump is not None:
            state.update(
                {
                    "Parameter": "1647",
                    "EnumValue": legionella_circulation_pump,
                    "Type": "1",
                },
            )
        if legionella_circulation_temp_diff is not None:
            state.update(
                {
                    "Parameter": "1648",
                    "Value": str(legionella_circulation_temp_diff),
                    "Type": "1",
                },
            )
        if dhw_circulation_pump_release is not None:
            state.update(
                {
                    "Parameter": "1660",
                    "EnumValue": dhw_circulation_pump_release,
                    "Type": "1",
                },
            )
        if dhw_circulation_pump_cycling is not None:
            state.update(
                {
                    "Parameter": "1661",
                    "Value": str(dhw_circulation_pump_cycling),
                    "Type": "1",
                },
            )
        if dhw_circulation_setpoint is not None:
            state.update(
                {
                    "Parameter": "1663",
                    "Value": str(dhw_circulation_setpoint),
                    "Type": "1",
                },
            )
        if operating_mode_changeover is not None:
            state.update(
                {
                    "Parameter": "1680",
                    "EnumValue": operating_mode_changeover,
                    "Type": "1",
                },
            )

        if dhw_time_programs:
            time_program_mapping = {
                "561": dhw_time_programs.monday,
                "562": dhw_time_programs.tuesday,
                "563": dhw_time_programs.wednesday,
                "564": dhw_time_programs.thursday,
                "565": dhw_time_programs.friday,
                "566": dhw_time_programs.saturday,
                "567": dhw_time_programs.sunday,
                "576": dhw_time_programs.standard_values,
            }

            for param, value in time_program_mapping.items():
                if value is not None:
                    state.update({"Parameter": param, "Value": value, "Type": "1"})

        if not state:
            raise BSBLANError(NO_STATE_ERROR_MSG)
        return state

    async def _set_hot_water_state(self, state: dict[str, Any]) -> None:
        """Set the hot water state.

        Args:
            state (dict[str, Any]): The state to set for the hot water.

        """
        response = await self._request(base_path="/JS", data=state)
        logger.debug("Response for setting: %s", response)
