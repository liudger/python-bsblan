"""Asynchronous Python client for BSB-Lan."""
import asyncio
import json
import socket
from typing import Any, Dict, Mapping, Optional, Tuple, Union

import aiohttp
import async_timeout
from yarl import URL

from .__version__ import __version__
from .exceptions import BSBLanConnectionError, BSBLanError
from .models import Device


class BSBLan:
    """Main class for handling connections with BSBLan."""

    device: Optional[Device] = None

    def __init__(
        self,
        host: str,
        base_path: str = "/JQ",
        loop: asyncio.events.AbstractEventLoop = None,
        port: int = 80,
        request_timeout: int = 30,
        session: aiohttp.client.ClientSession = None,
        username: str = None,
        password: str = None,
        user_agent: str = None,
        passkey: str = None,
    ) -> None:
        """Initialize connection with BSBLan."""
        self._loop = loop
        self._session = session
        self._close_session = False

        self.base_path = base_path
        self.host = host
        self.port = port
        self.socketaddr = None
        self.request_timeout = request_timeout
        self.username = username
        self.password = password
        self.user_agent = user_agent
        self.passkey = passkey

        if user_agent is None:
            self.user_agent = f"PythonBSBLan/{__version__}"

        if self.base_path[-1] != "/":
            self.base_path += "/"

    async def _request(
        self,
        uri: str,
        method: str = "POST",
        data: Optional[Any] = None,
        json_data: Optional[dict] = None,
        params: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """Handle a request to a BSBLan device."""
        # scheme = "https" if self.tls else "http"
        url = URL.build(
            scheme="http",
            host=self.host,
            port=self.port,
            path=self.base_path + self.passkey,
        ).join(URL(uri))

        auth = None
        if self.username and self.password:
            auth = aiohttp.BasicAuth(self.username, self.password)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
        }

        if self._loop is None:
            self._loop = asyncio.get_event_loop()

        if self._session is None:
            self._session = aiohttp.ClientSession(loop=self._loop)
            self._close_session = True

        try:
            with async_timeout.timeout(self.request_timeout):
                response = await self._session.request(
                    method,
                    url,
                    auth=auth,
                    data=data,
                    json=json_data,
                    params=params,
                    headers=headers,
                )
        except asyncio.TimeoutError as exception:
            raise BSBLanConnectionError(
                "Timeout occurred while connecting to BSBLan device."
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise BSBLanConnectionError(
                "Error occurred while communicating with BSBLan device."
            ) from exception

        content_type = response.headers.get("Content-Type", "")
        if (response.status // 100) in [4, 5]:
            contents = await response.read()
            response.close()

            if content_type == "application/json":
                raise BSBLanError(response.status, json.loads(contents.decode("utf8")))
            raise BSBLanError(response.status, {"message": contents.decode("utf8")})

        if "application/json" in content_type:
            return await response.json()

        return await response.text()

    async def state(self):

        pass

    async def info(self):

        pass

    async def currentTemperature(self):

        pass

    async def update(self) -> Optional[Device]:
        """Get all information about the device in a single call."""
        try:
            data = await self._request()
            self.device = Device.from_dict(data)
        except BSBLanError as exception:
            self.device = None
            raise exception

        return self.device

    async def light(
        self,
        brightness: Optional[int] = None,

    ) -> None:
        """Change state of a WLED Light segment."""
        if self.device is None:
            await self.update()

        if self.device is None:
            raise BSBLanError(
                "Unable to communicate with WLED to get the current state"
            )

        device = self.device

        state = {
            "bri": brightness,
        }

        # Filter out not set values
        state = {k: v for k, v in state.items() if v is not None}

        # Determine color set

        await self._request("state", method="POST", json_data=state)

        # Restore previous transition time
        if transition is None:
            await self._request(
                "state",
                method="POST",
                json_data={"transition": device.state.transition},
            )

    async def sync(
        self, send: Optional[bool] = None, receive: Optional[bool] = None
    ) -> None:
        """Set the sync status of the WLED device."""
        sync = {"send": send, "recv": receive}
        sync = {k: v for k, v in sync.items() if v is not None}
        await self._request("state", method="POST", json_data={"udpn": sync})

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
