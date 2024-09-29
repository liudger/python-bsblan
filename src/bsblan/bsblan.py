"""Asynchronous Python client for BSB-Lan."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, NoReturn, cast

import aiohttp
from aiohttp.hdrs import METH_POST
from aiohttp.helpers import BasicAuth
from packaging import version as pkg_version
from typing_extensions import Self
from yarl import URL

from .constants import (
    API_VERSION_ERROR_MSG,
    API_VERSIONS,
    FIRMWARE_VERSION_ERROR_MSG,
    HVAC_MODE_DICT,
    HVAC_MODE_DICT_REVERSE,
    MULTI_PARAMETER_ERROR_MSG,
    NO_STATE_ERROR_MSG,
    TEMPERATURE_RANGE_ERROR_MSG,
    VERSION_ERROR_MSG,
)
from .exceptions import (
    BSBLANConnectionError,
    BSBLANError,
    BSBLANInvalidParameterError,
    BSBLANVersionError,
)
from .models import Device, HotWaterState, Info, Sensor, State, StaticState

if TYPE_CHECKING:
    from aiohttp.client import ClientSession

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
    _api_data: dict[str, Any] | None = None

    async def __aenter__(self) -> Self:
        """Enter the context manager."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._close_session = True
        await self._initialize()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the context manager."""
        if self._close_session and self.session:
            await self.session.close()

    async def _initialize(self) -> None:
        """Initialize the BSBLAN client."""
        await self._fetch_firmware_version()
        await self._initialize_temperature_range()
        await self._initialize_api_data()

    async def _fetch_firmware_version(self) -> None:
        """Fetch the firmware version if not already available."""
        if self._firmware_version is None:
            device = await self.device()
            self._firmware_version = device.version
            logger.debug("BSBLAN version: %s", self._firmware_version)
            self._set_api_version()

    def _set_api_version(self) -> None:
        """Set the API version based on the firmware version."""
        if self._firmware_version:
            version = pkg_version.parse(self._firmware_version)
            if version < pkg_version.parse("1.2.0"):
                self._api_version = "v1"
            elif version >= pkg_version.parse("3.0.0"):
                self._api_version = "v3"
            else:
                raise BSBLANVersionError(VERSION_ERROR_MSG)
        else:
            raise BSBLANError(FIRMWARE_VERSION_ERROR_MSG)

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

    async def _initialize_api_data(self) -> None:
        """Initialize and cache the API data."""
        if self._api_data is None:
            if self._api_version is None:
                raise BSBLANError(API_VERSION_ERROR_MSG)
            self._api_data = API_VERSIONS[self._api_version]
            logger.debug("API data initialized for version: %s", self._api_version)

    async def _request(
        self,
        method: str = METH_POST,
        base_path: str = "/JQ",
        data: dict[str, object] | None = None,
        params: Mapping[str, str | int] | str | None = None,
    ) -> dict[str, Any]:
        """Handle a request to a BSBLAN device."""
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
                    return cast(dict[str, Any], await response.json())
        except asyncio.TimeoutError as e:
            raise BSBLANConnectionError(BSBLANConnectionError.message_timeout) from e
        except aiohttp.ClientError as e:
            raise BSBLANConnectionError(BSBLANConnectionError.message_error) from e
        except ValueError as e:
            raise BSBLANError(str(e)) from e

    def _build_url(self, base_path: str) -> URL:
        """Build the URL for the request."""
        if self.config.passkey:
            base_path = f"/{self.config.passkey}{base_path}"
        return URL.build(
            scheme="http",
            host=self.config.host,
            port=self.config.port,
            path=base_path,
        )

    def _get_auth(self) -> BasicAuth | None:
        """Get the authentication for the request."""
        if self.config.username and self.config.password:
            return BasicAuth(self.config.username, self.config.password)
        return None

    def _get_headers(self) -> dict[str, str]:
        """Get the headers for the request."""
        return {
            "User-Agent": f"PythonBSBLAN/{self._firmware_version}",
            "Accept": "application/json, */*",
        }

    def _validate_single_parameter(self, *params: Any, error_msg: str) -> None:
        """Validate that exactly one parameter is provided."""
        if sum(param is not None for param in params) != 1:
            raise BSBLANError(error_msg)

    async def _get_parameters(self, params: dict[Any, Any]) -> dict[Any, Any]:
        """Get the parameters info from BSBLAN device."""
        string_params = ",".join(map(str, params))
        return {"string_par": string_params, "list": list(params.values())}

    async def state(self) -> State:
        """Get the current state from BSBLAN device."""
        await self._initialize_api_data()
        params = await self._get_parameters(self._api_data["heating"])
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        data["hvac_mode"]["value"] = HVAC_MODE_DICT[int(data["hvac_mode"]["value"])]
        return State.from_dict(data)

    async def sensor(self) -> Sensor:
        """Get the sensor information from BSBLAN device."""
        await self._initialize_api_data()
        params = await self._get_parameters(self._api_data["sensor"])
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return Sensor.from_dict(data)

    async def static_values(self) -> StaticState:
        """Get the static information from BSBLAN device."""
        await self._initialize_api_data()
        params = await self._get_parameters(self._api_data["staticValues"])
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return StaticState.from_dict(data)

    async def device(self) -> Device:
        """Get BSBLAN device info."""
        device_info = await self._request(base_path="/JI")
        return Device.from_dict(device_info)

    async def info(self) -> Info:
        """Get information about the current heating system config."""
        await self._initialize_api_data()
        params = await self._get_parameters(self._api_data["device"])
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return Info.from_dict(data)

    async def thermostat(
        self,
        target_temperature: str | None = None,
        hvac_mode: str | None = None,
    ) -> None:
        """Change the state of the thermostat through BSB-Lan."""
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
        """Prepare the thermostat state for setting."""
        state: dict[str, Any] = {}
        if target_temperature is not None:
            self._validate_target_temperature(target_temperature)
            state.update({"Parameter": "710", "Value": target_temperature, "Type": "1"})
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
        """Validate the target temperature."""
        if self._min_temp is None or self._max_temp is None:
            raise BSBLANError(TEMPERATURE_RANGE_ERROR_MSG)

        def raise_invalid_parameter() -> NoReturn:
            raise BSBLANInvalidParameterError(target_temperature)

        try:
            temp = float(target_temperature)
            if not (self._min_temp <= temp <= self._max_temp):
                raise_invalid_parameter()
        except ValueError:
            raise_invalid_parameter()

    def _validate_hvac_mode(self, hvac_mode: str) -> None:
        """Validate the HVAC mode."""
        if hvac_mode not in HVAC_MODE_DICT_REVERSE:
            raise BSBLANInvalidParameterError(hvac_mode)

    async def _set_thermostat_state(self, state: dict[str, Any]) -> None:
        """Set the thermostat state."""
        response = await self._request(base_path="/JS", data=state)
        logger.debug("Response for setting: %s", response)

    async def hot_water_state(self) -> HotWaterState:
        """Get the current hot water state from BSBLAN device."""
        await self._initialize_api_data()
        params = await self._get_parameters(self._api_data["hot_water"])
        data = await self._request(params={"Parameter": params["string_par"]})
        data = dict(zip(params["list"], list(data.values()), strict=True))
        return HotWaterState.from_dict(data)

    async def set_hot_water(
        self,
        operating_mode: str | None = None,
        nominal_setpoint: float | None = None,
        reduced_setpoint: float | None = None,
    ) -> None:
        """Change the state of the hot water system through BSB-Lan."""
        self._validate_single_parameter(
            operating_mode,
            nominal_setpoint,
            reduced_setpoint,
            error_msg=MULTI_PARAMETER_ERROR_MSG,
        )

        state = self._prepare_hot_water_state(
            operating_mode,
            nominal_setpoint,
            reduced_setpoint,
        )
        await self._set_hot_water_state(state)

    def _prepare_hot_water_state(
        self,
        operating_mode: str | None,
        nominal_setpoint: float | None,
        reduced_setpoint: float | None,
    ) -> dict[str, Any]:
        """Prepare the hot water state for setting."""
        state: dict[str, Any] = {}
        if operating_mode is not None:
            state.update(
                {"Parameter": "1600", "EnumValue": operating_mode, "Type": "1"},
            )
        if nominal_setpoint is not None:
            state.update(
                {"Parameter": "1610", "Value": str(nominal_setpoint), "Type": "1"},
            )
        if reduced_setpoint is not None:
            state.update(
                {"Parameter": "1612", "Value": str(reduced_setpoint), "Type": "1"},
            )
        if not state:
            raise BSBLANError(NO_STATE_ERROR_MSG)
        return state

    async def _set_hot_water_state(self, state: dict[str, Any]) -> None:
        """Set the hot water state."""
        response = await self._request(base_path="/JS", data=state)
        logger.debug("Response for setting: %s", response)
