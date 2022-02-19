"""Asynchronous Python client for BSB-Lan."""
from __future__ import annotations

import asyncio
import logging
import socket
from asyncio.log import logger
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, TypedDict

import async_timeout
from aiohttp.client import ClientError, ClientResponseError, ClientSession
from aiohttp.hdrs import METH_POST
from aiohttp.helpers import BasicAuth
from packaging import version
from yarl import URL

from .exceptions import BSBLANConnectionError, BSBLANError
from .models import (
    DEVICE_INFO_API_V1,
    DEVICE_INFO_API_V2,
    HEATING_CIRCUIT1_API_V1,
    HEATING_CIRCUIT1_API_V2,
    Device,
    Info,
    State,
)

logging.basicConfig(level=logging.DEBUG)


@dataclass
class BSBLAN:
    """Main class for handling connections with BSBLAN."""

    host: str
    username: str | None = None
    password: str | None = None
    passkey: str | None = None
    port: int = 80
    request_timeout: int = 8
    session: ClientSession | None = None

    _version: str = ""
    _heatingcircuit1: str | None = None
    _heating_params: list[str] | None = None
    _info: str | None = None
    _device_params: list = field(default_factory=list)
    _auth: BasicAuth | None = None
    _close_session: bool = False

    async def _request(
        self,
        method: str = METH_POST,
        base_path: str = "/JQ",
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Handle a request to a BSBLAN device.

        A generic method for sending/handling HTTP requests done against
        the BSBLAN API.

        Args:
            method: HTTP method to use.
            base_path: Base path to use.
            data: Dictionary of data to send to the BSBLAN device.
            params: string of parameters to send to the BSBLAN device to
                retrieve certain data.

        Returns:
            A Python dictionary (Json decoded) with the response from
            the BSBLAN API.

        Raises:
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
            scheme="http", host=self.host, port=self.port, path=base_path
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
            raise BSBLANConnectionError(
                "Timeout occurred while connecting to BSBLAN device."
            ) from exception
        except (
            ClientError,
            ClientResponseError,
            socket.gaierror,
        ) as exception:
            raise BSBLANConnectionError(
                "Error occurred while communicating with BSBLAN device."
            ) from exception

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            text = await response.text()
            raise BSBLANError(
                "Unexpected response from the BSBLAN device",
                {"Content-Type": content_type, "response": text},
            )

        return await response.json()

    async def _scan(self, parameters: list) -> str:
        """Scan for parameters that return a value.

        Args:
            parameters: List of parameters to scan.

        Returns:
            String of valid parameters.

        """

        # convert list to string
        _parameters = ",".join(map(str, parameters))
        data = await self._request(params={"Parameter": f"{_parameters}"})
        notValidData = []
        notValidData2 = []
        for k, v in data.items():
            if not v.get("value"):
                notValidData.append(k)
            if v.get("value") == "---":
                notValidData2.append(k)

        # remove parameters with no returning value
        for i in notValidData or notValidData2:
            data.pop(i)

        # join parameters to create one string
        parameters = []
        for i in data.keys():
            parameters.append(i)
        _parameters = ",".join(map(str, parameters))

        return _parameters

    def _getList(self, dictionary) -> list[str]:
        """Get list of keys from a dictionary.

        Args:
            dictionary: Dictionary to get keys from.

        Returns:
            List of keys from the dictionary.
        """
        return [*dictionary]

    async def state(self) -> State:
        """Get the current state from BSBLAN device.

        Returns:
            A BSBLAN state object.

        Raises:
            BSBLANError: If version from the BSBLAN device an unsupported.

        """
        # get version
        if not self._version:
            await self.get_version()

        # retrieve heating circuit 1 and heating params so we can build the
        # data structure (its circuit 1 because it can support 2 circuits)
        if not self._heatingcircuit1 and not self._heating_params:
            await self._get_data_heatingcircuit()

        logging.debug("get state heatingcircuit1")
        data = await self._request(params={"Parameter": f"{self._heatingcircuit1}"})
        if self._heating_params is None:
            raise BSBLANError("state data is empty")
        else:
            data = dict(zip(self._heating_params, list(data.values())))
            return State.parse_obj(data)

    async def _get_data_heatingcircuit(self) -> None:
        """Get the data structure from BSBLAN device.

        Raises:
            BSBLANError: If version from the BSBLAN device an unsupported.

        """

        try:
            if version.parse(self._version) < version.parse("1.2.0"):
                logging.debug("scanning for state Parameters api version < 1.2")
                parameters = self._getList(HEATING_CIRCUIT1_API_V1)
                self._heatingcircuit1 = await self._scan(parameters)
                self._heating_params = list(HEATING_CIRCUIT1_API_V1.values())
            if (
                version.parse("3.0.0")
                > version.parse(self._version)  # noqa: W503
                >= version.parse("2.0.0")  # noqa: W503
            ):
                logging.debug("scanning for state Parameters api version 2.0")
                parameters = self._getList(HEATING_CIRCUIT1_API_V2)
                self._heatingcircuit1 = await self._scan(parameters)
                self._heating_params = list(HEATING_CIRCUIT1_API_V2.values())
        except BSBLANError as exception:
            raise BSBLANError(
                "BSBLAN device version is not supported, version: ", self._version
            ) from exception

    async def get_version(self) -> None:
        """Get the version from device."""
        self._device = await self.device()
        self._version = self._device.version
        logger.debug("version: %s", self._version)

    async def device(self) -> Device:
        """Get BSBLAN device info.

        Returns:
            A BSBLAN device info object.

        """
        _device = await self._request(base_path="/JI")
        logger.debug("device: %s", _device)
        return Device.parse_obj(_device)

    async def info(self) -> Info:
        """Get information about the current heating system config.

        Returns:
            A BSBLAN info object about the heating system.
        """
        if not self._version:
            await self.get_version()

        if not self._info:
            await self._get_data_info()

        data = await self._request(params={"Parameter": f"{self._info}"})
        data = dict(zip(self._device_params, list(data.values())))
        return Info.parse_obj(data)

    async def _get_data_info(self) -> None:
        """Get the parameters info from BSBLAN device."""

        if version.parse(self._version) < version.parse("1.2.0"):
            params = self._getList(DEVICE_INFO_API_V1)
            self._info = await self._scan(params)
            self._device_params = list(DEVICE_INFO_API_V1.values())
        if (
            version.parse("3.0.0")
            > version.parse(self._version)  # noqa: W503
            >= version.parse("2.0.0")  # noqa: W503
        ):
            params = self._getList(DEVICE_INFO_API_V2)
            self._info = await self._scan(params)
            self._device_params = list(DEVICE_INFO_API_V2.values())

    async def thermostat(
        self,
        target_temperature: str | None = None,
        hvac_mode: str | None = None,
    ) -> None:
        """Change the state of the thermostat through BSB-Lan.

        Args:
            target_temperature: Target temperature to set.
            hvac_mode: HVAC mode to set.

        Raises:
            BSBLANError: The provided values are invalid.
        """

        class ThermostatState(
            TypedDict, total=False
        ):  # lgtm [py/unused-local-variable]
            """Describe state dictionary that can be set on the thermostat."""

            target_temperature: str
            hvac_mode: str
            Parameter: str
            Value: str
            Type: str
            EnumValue: int

        state: ThermostatState = {}

        if target_temperature is not None:
            if not 7 <= float(target_temperature) <= 40:
                raise BSBLANError(
                    "Target temperature is not valid, must be between 7 and 40"
                )
            # TODO: create a basemodel object
            state["Parameter"] = "710"
            state["Value"] = target_temperature
            state["Type"] = "1"

        # TODO: clean up this code with basemodel
        _dict_hvac_mode = {
            "protection": 0,
            "auto": 1,
            "reduced": 2,
            "comfort": 3,
        }

        if hvac_mode is not None:
            if hvac_mode not in _dict_hvac_mode:
                raise BSBLANError("HVAC mode is not valid")
            # TODO: create a basemodel object
            state["Parameter"] = "700"
            state["EnumValue"] = _dict_hvac_mode[hvac_mode]
            state["Type"] = "1"

        if not state:
            raise BSBLANError("No state provided")

        # Type needs to be 1 to really set value.
        # Now it only checks if it could set value.
        response = await self._request(base_path="/JS", data=dict(state))
        logger.debug("response: %s", response)

    async def close(self) -> None:
        """Close open client session."""
        if self.session and self._close_session:
            await self.session.close()

    async def __aenter__(self) -> BSBLAN:
        """Async enter.

        Returns:
            The BSBLAN object.
        """

        return self

    async def __aexit__(self, *exc_info) -> None:
        """Async exit.

        Args:
            *exc_info: Exec type.
        """
        await self.close()
