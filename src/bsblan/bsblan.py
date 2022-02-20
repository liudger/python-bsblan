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
from packaging import version as pkg_version
from yarl import URL

from .constants import (
    DEVICE_INFO_API_V1,
    DEVICE_INFO_API_V2,
    HEATING_CIRCUIT1_API_V1,
    HEATING_CIRCUIT1_API_V2,
    HVAC_MODE_DICT,
)
from .exceptions import BSBLANConnectionError, BSBLANError
from .models import Device, Info, State

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
        not_valid_data = []
        not_valid_data2 = []
        for key, value in data.items():
            if not value.get("value"):
                not_valid_data.append(key)
            if value.get("value") == "":
                not_valid_data2.append(key)

        # remove parameters with no returning value
        for i in not_valid_data or not_valid_data2:
            data.pop(i)

        # join parameters to create one string
        parameters = []
        for i in data.keys():
            parameters.append(i)
        _parameters = ",".join(map(str, parameters))

        return _parameters

    async def state(self) -> State:
        """Get the current state from BSBLAN device.

        Returns:
            A BSBLAN state object.
        """
        if not self._heatingcircuit1 or not self._heating_params:
            data = await self._get_dict_version()
            logger.debug("data: %s", data)
            data = await self._get_parameters(data["heating"])
            self._heatingcircuit1 = str(data["string_par"])
            self._heating_params = list(data["list"])

        # retrieve heating circuit 1 and heating params so we can build the
        # data structure (its circuit 1 because it can support 2 circuits)
        logger.debug("get state")
        data = await self._request(params={"Parameter": f"{self._heatingcircuit1}"})
        data = dict(zip(self._heating_params, list(data.values())))
        return State.parse_obj(data)

    async def _get_dict_version(self) -> dict:
        """Get the version from device.

        Returns:
            A dictionary with dicts

        """
        if not self._version:
            device = await self.device()
            self._version = device.version
            logger.debug("BSBLAN version: %s", self._version)
        if pkg_version.parse(self._version) < pkg_version.parse("1.2.0"):
            return {"heating": HEATING_CIRCUIT1_API_V1, "device": DEVICE_INFO_API_V1}
        if (
            pkg_version.parse("3.0.0")
            > pkg_version.parse(self._version)  # noqa: W503
            >= pkg_version.parse("2.0.0")  # noqa: W503
        ):
            return {"heating": HEATING_CIRCUIT1_API_V2, "device": DEVICE_INFO_API_V2}
        return {}

    async def device(self) -> Device:
        """Get BSBLAN device info.

        Returns:
            A BSBLAN device info object.

        """
        device_info = await self._request(base_path="/JI")
        return Device.parse_obj(device_info)

    async def info(self) -> Info:
        """Get information about the current heating system config.

        Returns:
            A BSBLAN info object about the heating system.
        """
        if not self._info or not self._device_params:
            device_dict = await self._get_dict_version()
            data = await self._get_parameters(device_dict["device"])
            self._info = str(data["string_par"])
            self._device_params = data["list"]

        data = await self._request(params={"Parameter": f"{self._info}"})
        data = dict(zip(self._device_params, list(data.values())))
        return Info.parse_obj(data)

    async def _get_parameters(self, params: dict) -> dict:
        """Get the parameters info from BSBLAN device.

        Args:
            params: A dictionary with the parameters to get.

        Returns:
            A list of 2 objects [str, list].
        """
        list_params = [*params]
        parameters = await self._scan(list_params)
        logger.debug("parameters from scan: %s", parameters)
        object_parameters = list(params.values())

        return {"string_par": parameters, "list": object_parameters}

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

        class ThermostatState(  # lgtm [py/unused-local-variable]
            TypedDict, total=False
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
            if not 7 <= float(target_temperature) <= 40:
                raise BSBLANError(
                    "Target temperature is not valid, must be between 7 and 40"
                )
            state["Parameter"] = "710"
            state["Value"] = target_temperature
            state["Type"] = "1"

        if hvac_mode is not None:
            if hvac_mode not in HVAC_MODE_DICT:
                raise BSBLANError("HVAC mode is not valid")
            state["Parameter"] = "700"
            state["EnumValue"] = HVAC_MODE_DICT[hvac_mode]
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
