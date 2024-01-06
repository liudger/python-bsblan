"""Asynchronous Python client for BSB-Lan."""
from __future__ import annotations

import asyncio
import logging
import socket
from asyncio.log import logger
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, TypedDict, cast

import async_timeout
import backoff
from aiohttp.client import ClientError, ClientResponseError, ClientSession
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
from .exceptions import BSBLANConnectionError, BSBLANError
from .models import Device, Info, Sensor, State, StaticState

logging.basicConfig(level=logging.DEBUG)


@dataclass
class BSBLAN:
    """Main class for handling connections with BSBLAN."""

    host: str
    username: str | None = None
    password: str | None = None
    passkey: str | None = None
    port: int = 80
    request_timeout: int = 10
    session: ClientSession | None = None
    _version: str = ""
    _heating_params: list[str] | None = None
    _string_circuit1: str | None = None
    _sensor_params: list[str] | None = None
    _sensor_list: str | None = None
    _static_params: list[str] | None = None
    _static_list: str | None = None
    _device_params: list[str] = field(default_factory=list)
    _min_temp: float = 7.0
    _max_temp: float = 25.0
    _info: str | None = None
    _auth: BasicAuth | None = None
    _close_session: bool = False

    # cSpell:ignore BSBLAN
    @backoff.on_exception(backoff.expo, BSBLANConnectionError, max_tries=3, logger=None)
    async def _request(
        self,
        method: str = METH_POST,
        base_path: str = "/JQ",
        data: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
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
        try:
            version = metadata.version(__package__ or __name__)
        except metadata.PackageNotFoundError:
            version = "0.0.0"

        # retrieve passkey for custom url
        if self.passkey is not None:
            base_path = f"/{self.passkey}{base_path}"

        url = URL.build(
            scheme="http",
            host=self.host,
            port=self.port,
            path=base_path,
        ).join(URL())

        if self._auth is None and self.username and self.password:
            self._auth = BasicAuth(self.username, self.password)

        headers = {
            "User-Agent": f"PythonBSBLAN/{version}",
            "Accept": "application/json, */*",
        }

        if self.session is None:
            self.session = ClientSession()
            self._close_session = True

        try:
            async with async_timeout.timeout(self.request_timeout):
                response = await self.session.request(
                    method,
                    url,
                    auth=self._auth,
                    params=params,
                    json=data,
                    headers=headers,
                )
                response.raise_for_status()
        except asyncio.TimeoutError as exception:
            raise BSBLANConnectionError(BSBLANConnectionError.message) from exception
        except (
            ClientError,
            ClientResponseError,
            socket.gaierror,
        ) as exception:
            raise BSBLANConnectionError(BSBLANConnectionError.message) from exception

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            text = await response.text()
            raise BSBLANError(BSBLANError.message + f" ({text})")

        return cast(dict[str, Any], await response.json())

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
        return State.model_validate(data)

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
        return Sensor.model_validate(data)

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
        return StaticState.model_validate(data)

    async def _get_dict_version(self) -> dict[Any, Any]:
        """Get the version from device.

        Returns
        -------
            A dictionary with dicts

        """
        if not self._version:
            device = await self.device()
            self._version = device.version
            logger.debug("BSBLAN version: %s", self._version)
        if pkg_version.parse(self._version) < pkg_version.parse("1.2.0"):
            return {
                "heating": HEATING_CIRCUIT1_API_V1,
                "staticValues": STATIC_VALUES_API_V1,
                "device": DEVICE_INFO_API_V1,
                "sensor": SENSORS_API_V1,
            }
        if pkg_version.parse(self._version) > pkg_version.parse("3.0.0"):
            return {
                "heating": HEATING_CIRCUIT1_API_V3,
                "staticValues": STATIC_VALUES_API_V3,
                "device": DEVICE_INFO_API_V3,
                "sensor": SENSORS_API_V3,
            }
        raise BSBLANError(VERSION_ERROR_MSG)

    async def device(self) -> Device:
        """Get BSBLAN device info.

        Returns
        -------
            A BSBLAN device info object.

        """
        device_info = await self._request(base_path="/JI")
        return Device.model_validate(device_info)

    async def info(self) -> Info:
        """Get information about the current heating system config.

        Returns
        -------
            A BSBLAN info object about the heating system.
        """
        if not self._info or not self._device_params:
            device_dict = await self._get_dict_version()
            data = await self._get_parameters(device_dict["device"])
            self._info = str(data["string_par"])
            self._device_params = data["list"]

        data = await self._request(params={"Parameter": f"{self._info}"})
        data = dict(zip(self._device_params, list(data.values()), strict=True))
        return Info.model_validate(data)

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
                raise BSBLANError(INVALID_VALUES_ERROR_MSG)
            state["Parameter"] = "710"
            state["Value"] = target_temperature
            state["Type"] = "1"

        if hvac_mode is not None:
            if hvac_mode not in HVAC_MODE_DICT_REVERSE:
                raise BSBLANError(INVALID_VALUES_ERROR_MSG)
            state["Parameter"] = "700"
            state["EnumValue"] = HVAC_MODE_DICT_REVERSE[hvac_mode]
            state["Type"] = "1"

        if not state:
            raise BSBLANError(NO_STATE_ERROR_MSG)

        # Type needs to be 1 to really set value.
        # Now it only checks if it could set value.
        response = await self._request(base_path="/JS", data=dict(state))
        logger.debug("response for setting: %s", response)

    async def close(self) -> None:
        """Close open client session."""
        if self.session and self._close_session:
            await self.session.close()

    async def __aenter__(self) -> Self:
        """Async enter.

        Returns
        -------
            The BSBLAN object.
        """
        logger.debug("BSBLAN: %s", self)
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Async exit.

        Args:
        ----
            *_exc_info: Exec type.
        """
        await self.close()
