"""API version resolution for the BSBLAN client.

Owns the policy that maps a device's reported version signals to a supported
API configuration version. The BSB-LAN JSON-API version (from ``/JV``) is the
documented, firmware-independent compatibility signal and is preferred when
available; the adapter firmware version (from ``/JI``) is used as a fallback
for very old firmware that does not expose ``/JV``.
"""

from __future__ import annotations

from packaging import version as pkg_version
from packaging.version import InvalidVersion

from .constants import (
    BASIC_API_VERSION,
    MIN_SUPPORTED_FIRMWARE,
    MIN_SUPPORTED_JSON_API,
    SUPPORTED_API_VERSION,
    V3_FIRMWARE_MINIMUM,
    V3_JSON_API_MINIMUM,
    ErrorMsg,
)
from .exceptions import BSBLANError, BSBLANVersionError


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
    """Resolve the API configuration version from reported device versions.

    The resolver is configured with the version floors and ``v3`` thresholds
    for both the JSON-API and firmware signals. Defaults use the library's
    named constants; custom thresholds can be supplied for testing.
    """

    def __init__(
        self,
        *,
        firmware_minimum: str = MIN_SUPPORTED_FIRMWARE,
        firmware_v3_minimum: str = V3_FIRMWARE_MINIMUM,
        json_api_minimum: str = MIN_SUPPORTED_JSON_API,
        json_api_v3_minimum: str = V3_JSON_API_MINIMUM,
    ) -> None:
        """Initialize the resolver with version policy thresholds.

        Args:
            firmware_minimum: Lowest supported adapter firmware version.
            firmware_v3_minimum: Firmware version at/above which "v3" is used.
            json_api_minimum: Lowest supported JSON-API version.
            json_api_v3_minimum: JSON-API version at/above which "v3" is used.

        """
        self._firmware_minimum = firmware_minimum
        self._firmware_v3_minimum = firmware_v3_minimum
        self._json_api_minimum = json_api_minimum
        self._json_api_v3_minimum = json_api_v3_minimum

    def resolve_config_version(
        self,
        *,
        json_api_version: str | None,
        firmware_version: str | None,
    ) -> str:
        """Resolve the API config version from the available version signals.

        The JSON-API version is preferred when present; otherwise the firmware
        version is used as a fallback.

        Args:
            json_api_version: The JSON-API version reported by ``/JV``, or None.
            firmware_version: The adapter firmware version from ``/JI``, or None.

        Returns:
            ``"v2"`` for the basic single-circuit config or ``"v3"`` for the
            full config.

        Raises:
            BSBLANError: If neither the JSON-API version nor the firmware
                version is available.
            BSBLANVersionError: If the reported version is not supported.

        """
        if json_api_version is not None:
            return _map_reported_version(
                json_api_version,
                minimum=self._json_api_minimum,
                v3_minimum=self._json_api_v3_minimum,
            )

        if not firmware_version:
            raise BSBLANError(ErrorMsg.FIRMWARE_VERSION)

        return _map_reported_version(
            firmware_version,
            minimum=self._firmware_minimum,
            v3_minimum=self._firmware_v3_minimum,
        )
