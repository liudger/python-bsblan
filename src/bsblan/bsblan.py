"""Asynchronous Python client for BSB-Lan."""

from __future__ import annotations

import asyncio
import logging
from asyncio.log import logger
from dataclasses import dataclass, field
from typing import Any, Mapping, TypedDict, cast

import aiohttp
from aiohttp.client import ClientSession
from aiohttp.hdrs import METH_POST
from aiohttp.helpers import BasicAuth
from packaging import version as pkg_version
from typing_extensions import Self
from yarl import URL

from .constants import (
    DEVICE_INFO_API_V1,
    DEVICE_INFO_API_V3,
    HEATING_CIRCUIT1_API_V1,
    HEATING_CIRCUIT1_API_V3,
    HOT_WATER_API_V1,
    HOT_WATER_API_V3,
    HVAC_MODE_DICT,
    HVAC_MODE_DICT_REVERSE,
    INVALID_VALUES_ERROR_MSG,
    NO_STATE_ERROR_MSG,
    SENSORS_API_V1,
    SENSORS_API_V3,
    STATIC_VALUES_API_V1,
    STATIC_VALUES_API_V3,
    VERSION_ERROR_MSG,
)
from .exceptions import (
    BSBLANConnectionError,
    BSBLANError,
    BSBLANInvalidParameterError,
    BSBLANVersionError,
)
from .models import Device, HotWaterState, Info, Sensor, State, StaticState

logging.basicConfig(level=logging.DEBUG)


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

    _heating_params: list[str] | None = None
    _string_circuit1: str | None = None
    _sensor_params: list[str] | None = None
    _sensor_list: str | None = None
    _hot_water_params: list[str] | None = None
    _hot_water_string: str | None = None
    _static_params: list[str] | None = None
    _static_list: str | None = None
    _device_params: list[str] = field(default_factory=list)
    _min_temp: float = 7.0
    _max_temp: float = 25.0
    _info_string: str | None = None
    _auth: BasicAuth | None = None
    _close_session: bool = False

    def __init__(
        self,
        config: BSBLANConfig,
        session: ClientSession | None = None,
    ) -> None:
        """Initialize the BSBLAN object.

        Args:
        ----
            config: Configuration for the BSBLAN object.
            session: The aiohttp session to use for the connection.

        """
        self.config = config
        self.session = session
        self._close_session = session is None
        self._firmware_version: str | None = None

    async def _fetch_firmware_version(self) -> None:
        """Fetch the firmware version if not already available."""
        if self._firmware_version is None:
            device = await self.device()
            self._firmware_version = device.version
            logger.debug("BSBLAN version: %s", self._firmware_version)

    async def __aenter__(self) -> Self:
        """Enter method for the context manager.

        Returns
        -------
            Self: The current instance of the context manager.

        """
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._close_session = True
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit method for the context manager.

        Args:
        ----
            *args: Arguments passed to the exit method.

        """
        if self._close_session and self.session:
            await self.session.close()

    # cSpell:ignore BSBLAN
    async def _request(
        self,
        method: str = METH_POST,
        base_path: str = "/JQ",
        data: dict[str, object] | None = None,
        params: Mapping[str, str | int] | str | None = None,
    ) -> dict[str, Any]:
        """Handle a request to a BSBLAN device.

        A generic method for sending/handling HTTP requests done against
        the BSBLAN API.

        Args:
        ----
            method: HTTP method to use.
            base_path: Base path to use.
            data: Dictionary of data to send to the BSBLAN device.
            params: string of parameters to send to the BSBLAN device to
                retrieve certain data.

        Returns:
        -------
            A Python dictionary (JSON decoded) with the response from
            the BSBLAN API.

        Raises:
        ------
            BSBLANConnectionError: If the connection to the BSBLAN device
                fails.
            BSBLANError: If receiving from the BSBLAN device an unexpected
                response.

        """
        # retrieve passkey for custom url
        if self.config.passkey:
            base_path = f"/{self.config.passkey}{base_path}"

        url = URL.build(
            scheme="http",
            host=self.config.host,
            port=self.config.port,
            path=base_path,
        )

        auth = None
        if self.config.username and self.config.password:
            auth = BasicAuth(self.config.username, self.config.password)

        headers = {
            "User-Agent": f"PythonBSBLAN/{self._firmware_version}",
            "Accept": "application/json, */*",
        }

        if self.session is None:
            self.session = ClientSession()
            self._close_session = True

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

    async def state(self) -> State:
        """Get the current state from BSBLAN device.

        Returns
        -------
            A BSBLAN state object.

        """
        if not self._string_circuit1 or not self._heating_params:
            # retrieve heating circuit 1
            data = await self._get_dict_version()
            data = await self._get_parameters(data["heating"])
            self._string_circuit1 = str(data["string_par"])
            self._heating_params = list(data["list"])

        # retrieve heating circuit 1 and heating params so we can build the
        # data structure (its circuit 1 because it can support 2 circuits)
        data = await self._request(params={"Parameter": f"{self._string_circuit1}"})
        data = dict(zip(self._heating_params, list(data.values()), strict=True))

        # set hvac_mode with correct value
        data["hvac_mode"]["value"] = HVAC_MODE_DICT[int(data["hvac_mode"]["value"])]
        return State.from_dict(data)

    async def sensor(self) -> Sensor:
        """Get the sensor information from BSBLAN device.

        Returns
        -------
            A BSBLAN sensor object.

        """
        if not self._sensor_params:
            data = await self._get_dict_version()
            data = await self._get_parameters(data["sensor"])
            self._sensor_list = str(data["string_par"])
            self._sensor_params = list(data["list"])

        # retrieve sensor params so we can build the data structure
        data = await self._request(params={"Parameter": f"{self._sensor_list}"})
        data = dict(zip(self._sensor_params, list(data.values()), strict=True))
        return Sensor.from_dict(data)

    async def static_values(self) -> StaticState:
        """Get the static information from BSBLAN device.

        Returns
        -------
            A BSBLAN staticState object.

        """
        if not self._static_params:
            data = await self._get_dict_version()
            data = await self._get_parameters(data["staticValues"])
            self._static_list = str(data["string_par"])
            self._static_params = list(data["list"])

        # retrieve sensor params so we can build the data structure
        data = await self._request(params={"Parameter": f"{self._static_list}"})
        data = dict(zip(self._static_params, list(data.values()), strict=True))
        self._min_temp = data["min_temp"]["value"]
        self._max_temp = data["max_temp"]["value"]
        return StaticState.from_dict(data)

    async def _get_dict_version(self) -> dict[Any, Any]:
        """Get the version from device.

        Returns
        -------
            A dictionary with dicts

        """
        await self._fetch_firmware_version()

        if self._firmware_version is None:
            msg = "Unable to fetch firmware version"
            raise BSBLANError(msg)

        if pkg_version.parse(self._firmware_version) < pkg_version.parse("1.2.0"):
            return {
                "heating": HEATING_CIRCUIT1_API_V1,
                "staticValues": STATIC_VALUES_API_V1,
                "device": DEVICE_INFO_API_V1,
                "sensor": SENSORS_API_V1,
                "hot_water": HOT_WATER_API_V1,
            }
        if pkg_version.parse(self._firmware_version) > pkg_version.parse("3.0.0"):
            return {
                "heating": HEATING_CIRCUIT1_API_V3,
                "staticValues": STATIC_VALUES_API_V3,
                "device": DEVICE_INFO_API_V3,
                "sensor": SENSORS_API_V3,
                "hot_water": HOT_WATER_API_V3,
            }
        raise BSBLANVersionError(VERSION_ERROR_MSG)

    async def device(self) -> Device:
        """Get BSBLAN device info.

        Returns
        -------
            A BSBLAN device info object.

        """
        device_info = await self._request(base_path="/JI")
        return Device.from_dict(device_info)

    async def info(self) -> Info:
        """Get information about the current heating system config.

        Returns
        -------
            A BSBLAN info object about the heating system.

        """
        if not self._info_string or not self._device_params:
            device_dict = await self._get_dict_version()
            data = await self._get_parameters(device_dict["device"])
            self._info_string = str(data["string_par"])
            self._device_params = data["list"]

        data = await self._request(params={"Parameter": f"{self._info_string}"})
        data = dict(zip(self._device_params, list(data.values()), strict=True))
        return Info.from_dict(data)

    async def _get_parameters(self, params: dict[Any, Any]) -> dict[Any, Any]:
        """Get the parameters info from BSBLAN device.

        Args:
        ----
            params: A dictionary with the parameters to get.

        Returns:
        -------
            A dict of 2 objects [str, list].

        """
        _string_params = [*params]
        list_params = list(params.values())
        # convert list of string to string
        string_params = ",".join(map(str, _string_params))

        return {"string_par": string_params, "list": list_params}

    async def thermostat(
        self,
        target_temperature: str | None = None,
        hvac_mode: str | None = None,
    ) -> None:
        """Change the state of the thermostat through BSB-Lan.

        Args:
        ----
            target_temperature: Target temperature to set.
            hvac_mode: Preset mode to set.

        Raises:
        ------
            BSBLANError: The provided values are invalid.

        """

        class ThermostatState(  # lgtm [py/unused-local-variable]
            TypedDict,
            total=False,
        ):
            """Describe state dictionary that can be set on the thermostat."""

            target_temperature: str
            hvac_mode: str
            Parameter: str
            Value: str
            Type: str
            EnumValue: int

        state: ThermostatState = {}

        if target_temperature is not None:
            if not (
                float(self._min_temp)
                <= float(target_temperature)
                <= float(self._max_temp)
            ):
                raise BSBLANInvalidParameterError(
                    INVALID_VALUES_ERROR_MSG + ": " + str(target_temperature),
                )
            state["Parameter"] = "710"
            state["Value"] = target_temperature
            state["Type"] = "1"

        if hvac_mode is not None:
            if hvac_mode not in HVAC_MODE_DICT_REVERSE:
                raise BSBLANInvalidParameterError(
                    INVALID_VALUES_ERROR_MSG + ": " + str(hvac_mode),
                )
            state["Parameter"] = "700"
            state["EnumValue"] = HVAC_MODE_DICT_REVERSE[hvac_mode]
            state["Type"] = "1"

        if not state:
            raise BSBLANError(NO_STATE_ERROR_MSG)

        # Type needs to be 1 to really set value.
        # Now it only checks if it could set value.
        response = await self._request(base_path="/JS", data=dict(state))
        logger.debug("response for setting: %s", response)

    async def hot_water_state(self) -> HotWaterState:
        """Get the current hot water state from BSBLAN device."""
        if not self._hot_water_string or not self._hot_water_params:
            data = await self._get_dict_version()
            data = await self._get_parameters(data["hot_water"])
            self._hot_water_string = str(data["string_par"])
            self._hot_water_params = list(data["list"])

        data = await self._request(params={"Parameter": f"{self._hot_water_string}"})
        data = dict(zip(self._hot_water_params, list(data.values()), strict=True))
        return HotWaterState.from_dict(data)

    async def set_hot_water(
        self,
        operating_mode: str | None = None,
        nominal_setpoint: float | None = None,
        reduced_setpoint: float | None = None,
    ) -> None:
        """Change the state of the hot water system through BSB-Lan."""
        state = {}

        if operating_mode is not None:
            state["Parameter"] = "1600"
            state["EnumValue"] = operating_mode
            state["Type"] = "1"

        if nominal_setpoint is not None:
            state["Parameter"] = "1610"
            state["Value"] = str(nominal_setpoint)
            state["Type"] = "1"

        if reduced_setpoint is not None:
            state["Parameter"] = "1612"
            state["Value"] = str(reduced_setpoint)
            state["Type"] = "1"

        if not state:
            raise BSBLANError(NO_STATE_ERROR_MSG)

        response = await self._request(base_path="/JS", data=dict(state))
        logger.debug("response for setting hot water: %s", response)
