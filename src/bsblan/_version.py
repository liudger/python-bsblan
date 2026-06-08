"""API capability resolution for the BSBLAN client.

Owns the policy that maps a device's reported BSB-LAN JSON-API version (from
``/JV``) to a supported API configuration. The JSON-API version is the
documented, firmware-independent compatibility signal and is the sole input for
selecting the configuration. The adapter firmware version (from ``/JI``) is
retrieved for informational purposes only and is not checked here.
"""

from __future__ import annotations

from packaging import version as pkg_version
from packaging.version import InvalidVersion

from .constants import (
    MIN_SUPPORTED_JSON_API,
    V3_JSON_API_MINIMUM,
    ErrorMsg,
)
from .exceptions import BSBLANVersionError


class VersionResolver:
    """Resolve the API capability from the JSON-API version.

    The resolver is configured with the JSON-API version floor and the full
    configuration threshold. Defaults use the library's named constants;
    custom thresholds can be supplied for testing.
    """

    def __init__(
        self,
        *,
        json_api_minimum: str = MIN_SUPPORTED_JSON_API,
        json_api_v3_minimum: str = V3_JSON_API_MINIMUM,
    ) -> None:
        """Initialize the resolver with version policy thresholds.

        Args:
            json_api_minimum: Lowest supported JSON-API version.
            json_api_v3_minimum: JSON-API version at/above which the full
                configuration is used.

        """
        self._json_api_minimum = json_api_minimum
        self._json_api_v3_minimum = json_api_v3_minimum

    def supports_full_config(self, *, json_api_version: str | None) -> bool:
        """Determine whether the device supports the full configuration.

        The BSB-LAN JSON-API version reported by ``/JV`` is the sole signal for
        selecting the configuration. The adapter firmware version is not
        considered.

        Args:
            json_api_version: The JSON-API version reported by ``/JV``, or None.

        Returns:
            ``True`` when the full configuration is supported, ``False`` for the
            basic single-circuit configuration.

        Raises:
            BSBLANVersionError: If the JSON-API version is unavailable or the
                reported version is not supported.

        """
        if json_api_version is None:
            raise BSBLANVersionError(ErrorMsg.VERSION)
        try:
            parsed = pkg_version.parse(json_api_version)
        except InvalidVersion as exc:
            raise BSBLANVersionError(
                ErrorMsg.VERSION, version=json_api_version
            ) from exc
        if parsed < pkg_version.parse(self._json_api_minimum):
            raise BSBLANVersionError(ErrorMsg.VERSION, version=json_api_version)
        return parsed >= pkg_version.parse(self._json_api_v3_minimum)
