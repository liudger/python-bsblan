"""HTTP transport layer for the BSBLAN client.

Owns the low-level concerns of talking to a BSB-LAN device: URL building,
authentication, headers, request execution with exponential-backoff retries,
and firmware-specific response post-processing. The owning client keeps a
stable ``_request`` facade that delegates here.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, cast

import aiohttp
import backoff
from aiohttp.helpers import BasicAuth
from packaging import version as pkg_version
from yarl import URL

from .constants import ErrorMsg
from .exceptions import BSBLANAuthError, BSBLANError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from aiohttp.client import ClientSession

    from .bsblan import BSBLANConfig

logger = logging.getLogger(__name__)

# HTTP status that must not be retried (resource genuinely absent).
HTTP_NOT_FOUND = 404
# HTTP statuses that indicate authentication failure (not retried).
HTTP_AUTH_STATUSES = (401, 403)
# Firmware version at/after which /JQ responses include a debug `payload` field.
PAYLOAD_FIELD_MIN_VERSION = "5.0.0"


def _should_give_up_retry(error: Exception) -> bool:
    """Return whether a failed request must not be retried.

    Args:
        error: The exception raised while performing the request.

    Returns:
        bool: True for HTTP 404 responses, which are not transient.

    """
    return (
        isinstance(error, aiohttp.ClientResponseError)
        and error.status == HTTP_NOT_FOUND
    )


class BSBLANTransport:
    """Handle HTTP transport for a BSB-LAN device.

    The session and firmware version are read through callables because both
    are assigned on the owning client after it is constructed (the session in
    ``__aenter__`` and the firmware version during ``initialize``).
    """

    def __init__(
        self,
        config: BSBLANConfig,
        session_getter: Callable[[], ClientSession | None],
        firmware_getter: Callable[[], str | None],
    ) -> None:
        """Initialize the transport.

        Args:
            config: Connection configuration (host, port, credentials, timeout).
            session_getter: Callable returning the current client session.
            firmware_getter: Callable returning the current firmware version.

        """
        self._config = config
        self._session_getter = session_getter
        self._firmware_getter = firmware_getter

    @backoff.on_exception(
        backoff.expo,
        (TimeoutError, aiohttp.ClientError),
        max_tries=3,
        max_time=30,
        giveup=_should_give_up_retry,
        logger=logger,
    )
    async def request_with_retry(
        self,
        method: str,
        base_path: str,
        data: dict[str, object] | None,
        params: Mapping[str, str | int] | str | None,
    ) -> dict[str, Any]:
        """Execute an HTTP request with automatic retries.

        Decorated with backoff for automatic retries on transient failures.

        Args:
            method: The HTTP method to use.
            base_path: The base path for the URL.
            data: The data to send in the request body.
            params: The query parameters to include.

        Returns:
            dict[str, Any]: The JSON response from the BSBLAN device.

        Raises:
            BSBLANError: If the session is missing or the response is invalid.
            BSBLANAuthError: If authentication fails (401/403, not retried).

        """
        session = self._session_getter()
        if session is None:
            raise BSBLANError(ErrorMsg.SESSION_NOT_INITIALIZED)
        url = self._build_url(base_path)
        auth = self._get_auth()
        headers = self._get_headers()

        try:
            async with asyncio.timeout(self._config.request_timeout):
                async with session.request(
                    method,
                    url,
                    auth=auth,
                    params=params,
                    json=data,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    response_data = await self._read_json(response)
                    return self._process_response(response_data, base_path)
        except aiohttp.ClientResponseError as e:
            if e.status in HTTP_AUTH_STATUSES:
                raise BSBLANAuthError from e
            raise
        except (ValueError, UnicodeDecodeError) as e:
            # Handle JSON decode errors and other parsing issues
            msg = ErrorMsg.INVALID_RESPONSE.format(e)
            raise BSBLANError(msg) from e

    @staticmethod
    async def _read_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
        """Decode a BSB-LAN JSON response tolerant of non-UTF-8 encodings.

        Some BSB-LAN firmwares serve custom parameter descriptions using
        Latin-1 (ISO-8859-1) bytes (for example the ``§`` or ``°`` characters)
        while declaring no charset. ``aiohttp`` assumes UTF-8 and raises
        ``UnicodeDecodeError``. Read the raw body and fall back to Latin-1,
        which can decode any byte sequence, before parsing the JSON.

        Args:
            response: The active aiohttp response to read.

        Returns:
            dict[str, Any]: The parsed JSON payload.

        Raises:
            ValueError: If the body is not valid JSON.

        """
        raw = await response.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        return cast("dict[str, Any]", json.loads(text))

    def _process_response(
        self, response_data: dict[str, Any], base_path: str
    ) -> dict[str, Any]:
        """Process response data based on firmware version.

        BSB-LAN 5.0+ includes an additional 'payload' field in /JQ responses
        that needs to be handled for compatibility.

        Args:
            response_data: Raw response data from BSB-LAN.
            base_path: The API endpoint that was called.

        Returns:
            Processed response data compatible with existing code.

        """
        # For non-JQ endpoints, return response as-is
        if base_path != "/JQ":
            return response_data

        # Check if we have a firmware version to determine processing
        firmware_version = self._firmware_getter()
        if not firmware_version:
            return response_data

        # For BSB-LAN 5.0+, remove 'payload' field if present (debugging only)
        version = pkg_version.parse(firmware_version)
        if (
            version >= pkg_version.parse(PAYLOAD_FIELD_MIN_VERSION)
            and "payload" in response_data
        ):
            return {k: v for k, v in response_data.items() if k != "payload"}

        return response_data

    def _build_url(self, base_path: str) -> URL:
        """Build the URL for the request.

        Args:
            base_path (str): The base path for the URL.

        Returns:
            URL: The constructed URL.

        """
        if self._config.passkey:
            base_path = f"/{self._config.passkey}{base_path}"
        return URL.build(
            scheme="http",
            host=self._config.host,
            port=self._config.port,
            path=base_path,
        )

    def _get_auth(self) -> BasicAuth | None:
        """Get the authentication for the request.

        Returns:
            BasicAuth | None: The authentication object or None if no
                authentication is required.

        """
        if self._config.username and self._config.password:
            return BasicAuth(self._config.username, self._config.password)
        return None

    def _get_headers(self) -> dict[str, str]:
        """Get the headers for the request.

        Returns:
            dict[str, str]: The headers for the request.

        """
        return {
            "User-Agent": f"PythonBSBLAN/{self._firmware_getter()}",
            "Accept": "application/json, */*",
        }
