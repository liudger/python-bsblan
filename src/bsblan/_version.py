"""API version resolution for the BSBLAN client.

Owns the policy that maps a device's reported BSB-LAN JSON-API version (from
``/JV``) to a supported API configuration version. The JSON-API version is the
documented, firmware-independent compatibility signal and is the sole input for
selecting the configuration. The adapter firmware version (from ``/JI``) is
retrieved for informational purposes only and is not checked here.
"""

from __future__ import annotations

from packaging import version as pkg_version
from packaging.version import InvalidVersion

from .constants import (
    BASIC_API_VERSION,
    MIN_SUPPORTED_JSON_API,
    SUPPORTED_API_VERSION,
    V3_JSON_API_MINIMUM,
    ErrorMsg,
)
from .exceptions import BSBLANVersionError


def _map_reported_version(reported: str, *, minimum: str, v3_minimum: str) -> str:
    """Map a reported version string to a supported API config version.

    Args:
        reported: The version string reported by the device.
        minimum: The lowest supported version; anything below is rejected.
        v3_minimum: The threshold at or above which the full "v3" config is
            used; below it the basic "v2" config is used.

    Returns:
        ``"v2"`` for the basic single-circuit config or ``"v3"`` for the full
        config.

    Raises:
        BSBLANVersionError: If the reported version cannot be parsed or is
            below ``minimum``.

    """
    try:
        parsed = pkg_version.parse(reported)
    except InvalidVersion as exc:
        raise BSBLANVersionError(ErrorMsg.VERSION, version=reported) from exc
    if parsed < pkg_version.parse(minimum):
        raise BSBLANVersionError(ErrorMsg.VERSION, version=reported)
    if parsed < pkg_version.parse(v3_minimum):
        # Legacy / basic capability: single-circuit support only.
        return BASIC_API_VERSION
    return SUPPORTED_API_VERSION


class VersionResolver:
    """Resolve the API configuration version from the JSON-API version.

    The resolver is configured with the JSON-API version floor and the ``v3``
    threshold. Defaults use the library's named constants; custom thresholds
    can be supplied for testing.
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
            json_api_v3_minimum: JSON-API version at/above which "v3" is used.

        """
        self._json_api_minimum = json_api_minimum
        self._json_api_v3_minimum = json_api_v3_minimum

    def resolve_config_version(self, *, json_api_version: str | None) -> str:
        """Resolve the API config version from the JSON-API version.

        The BSB-LAN JSON-API version reported by ``/JV`` is the sole signal for
        selecting the configuration. The adapter firmware version is not
        considered.

        Args:
            json_api_version: The JSON-API version reported by ``/JV``, or None.

        Returns:
            ``"v2"`` for the basic single-circuit config or ``"v3"`` for the
            full config.

        Raises:
            BSBLANVersionError: If the JSON-API version is unavailable or the
                reported version is not supported.

        """
        if json_api_version is None:
            raise BSBLANVersionError(ErrorMsg.VERSION)

        return _map_reported_version(
            json_api_version,
            minimum=self._json_api_minimum,
            v3_minimum=self._json_api_v3_minimum,
        )
