"""Asynchronous Python client for BSB-Lan."""
import asyncio
import logging
import socket
from typing import Any, Mapping, Optional

import aiohttp
import async_timeout
from yarl import URL

from .__version__ import __version__
from .exceptions import BSBLanConnectionError, BSBLanError
from .models import Info, State

logging.basicConfig(level=logging.DEBUG)


class BSBLan:
    """Main class for handling connections with BSBLan."""

    def __init__(
        self,
        host: str,
        port: int = 80,
        request_timeout: int = 8,
        session: aiohttp.client.ClientSession = None,
        username: str = None,
        password: str = None,
        passkey: str = None,
    ) -> None:
        """Initialize connection with BSBLan."""
        self._session = session
        self._close_session = False
        self.host = host
        self.port = port
        self.request_timeout = request_timeout
        self.username = username
        self.password = password
        self.passkey = passkey
        self._heatingcircuit1: list = []

    async def _request(
        self,
        method: str = "POST",
        data: Optional[dict] = None,
        params: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """Handle a request to a BSBLan device."""

        base_path = "/JQ" if data is None else "/JS"
        if self.passkey is not None:
            base_path = f"/{self.passkey}{base_path}"

        url = URL.build(
            scheme="http", host=self.host, port=self.port, path=base_path
        ).join(URL())

        auth = None
        if self.username and self.password:
            auth = aiohttp.BasicAuth(self.username, self.password)

        headers = {
            "User-Agent": f"PythonBSBLan/{__version__}",
            "Accept": "application/json, */*",
        }

        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True

        try:
            async with async_timeout.timeout(self.request_timeout):
                response = await self._session.request(
                    method,
                    url,
                    auth=auth,
                    params=params,
                    json=data,
                    headers=headers,
                )
                response.raise_for_status()
        except asyncio.TimeoutError as exception:
            raise BSBLanConnectionError(
                "Timeout occurred while connecting to BSBLan device."
            ) from exception
        except (
            aiohttp.ClientError,
            aiohttp.ClientResponseError,
            socket.gaierror,
        ) as exception:
            raise BSBLanConnectionError(
                "Error occurred while communicating with BSBLan device."
            ) from exception

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            text = await response.text()
            raise BSBLanError(
                "Unexpected response from the BSBLan device",
                {"Content-Type": content_type, "response": text},
            )
        return await response.json()

    async def _scan(self, parameters) -> list:
        """Scan for parameters that return a value.

        input: list to scan

        output: string for scanning the valid params

        """
        # We should add parameters here using scan function.
        # By default we need a list with basic params.

        # convert list to string
        parameters = ",".join(str(e) for e in parameters)
        data = await self._request(params={"Parameter": f"{parameters}"})
        logging.debug("data: %s", data)
        notValidData = []
        notValidData2 = []
        for k, v in data.items():
            if not v.get("value"):
                # print(f"Invalid: {k}")
                notValidData.append(k)
            if v.get("value") == "---":
                notValidData2.append(k)

        # remove parameters with no returning value
        # print(f"DataNotValid: {notValidData} and {notValidData2}")
        for i in notValidData or notValidData2:
            data.pop(i)

        # join parameters to create one string
        parameters = []
        for i in data.keys():
            parameters.append(i)
        parameters = ",".join(parameters)
        logging.debug("params: %s", parameters)

        return parameters

    async def state(self) -> State:
        """Get the current state from BSBLan device."""

        if not self._heatingcircuit1:
            logging.info("scanning for state Parameters")
            parameters = State.heating_circuit1

            self._heatingcircuit1 = await self._scan(parameters)
        logging.info("get state heatingcircuit1")
        data = await self._request(params={"Parameter": f"{self._heatingcircuit1}"})

        return State.from_dict(data)

    async def info(self) -> Info:
        """Get information about the current heating system config."""
        data = await self._request(params={"Parameter": "6224,6225,6226"})
        return Info.from_dict(data)

    async def thermostat(
        self,
        target_temperature: Optional[str] = None,
        hvac_mode: Optional[str] = None,
    ) -> None:
        """Change the state of the thermostat through BSB-Lan."""

        state = {}

        if target_temperature is not None:
            state["Parameter"] = "710"
            state["Value"] = target_temperature
            state["Type"] = "1"
        if hvac_mode is not None:
            state["Parameter"] = "700"
            state["EnumValue"] = hvac_mode
            state["Type"] = "1"
        # Type needs to be 1 to really set value.
        # Now it only checks if it could set value.
        response = await self._request(data=state)
        logging.info("response: %s", response)
        # return Thermostat.from_dict(data)

    async def close(self) -> None:
        """Close open client session."""
        if self._session and self._close_session:
            await self._session.close()

    async def __aenter__(self) -> "BSBLan":
        """Async enter."""
        return self

    async def __aexit__(self, *exc_info) -> None:
        """Async exit."""
        await self.close()
