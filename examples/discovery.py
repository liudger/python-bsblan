"""Discovery utility for finding BSB-LAN devices on the network.

Uses mDNS/Zeroconf to discover BSB-LAN devices without needing hardcoded IPs.

Usage:
    from discovery import discover_bsblan, get_bsblan_host

    # Get host (from env or mDNS discovery)
    host, port = await get_bsblan_host()

    # Or discover all devices
    devices = await discover_bsblan()
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Self

from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

# BSB-LAN mDNS service type
BSBLAN_SERVICE_TYPE = "_http._tcp.local."
BSBLAN_NAME_PREFIX = "bsb-lan"

# Environment variable names for credentials
ENV_BSBLAN_HOST = "BSBLAN_HOST"
ENV_BSBLAN_USER = "BSBLAN_USER"
ENV_BSBLAN_PASS = "BSBLAN_PASS"  # noqa: S105
ENV_BSBLAN_PASSKEY = "BSBLAN_PASSKEY"
ENV_BSBLAN_PORT = "BSBLAN_PORT"

# Default discovery wait time
DEFAULT_DISCOVERY_SECONDS = 5.0


@dataclass
class DiscoveredDevice:
    """Represents a discovered BSB-LAN device."""

    name: str
    host: str
    port: int
    addresses: list[str]

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.name} at {self.host}:{self.port}"


class BSBLANDiscovery:
    """Async context manager for discovering BSB-LAN devices via mDNS."""

    def __init__(self, discovery_seconds: float = DEFAULT_DISCOVERY_SECONDS) -> None:
        """Initialize discovery.

        Args:
            discovery_seconds: How long to wait for device discovery in seconds.

        """
        self.discovery_seconds = discovery_seconds
        self.devices: list[DiscoveredDevice] = []
        self._aiozc: AsyncZeroconf | None = None
        self._browser: AsyncServiceBrowser | None = None

    async def __aenter__(self) -> Self:
        """Enter async context."""
        self._aiozc = AsyncZeroconf()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context and cleanup."""
        if self._browser:
            await self._browser.async_cancel()
        if self._aiozc:
            await self._aiozc.async_close()

    async def discover(self) -> list[DiscoveredDevice]:
        """Discover BSB-LAN devices on the network.

        Returns:
            List of discovered BSB-LAN devices.

        """
        if not self._aiozc:
            msg = "Discovery must be used as async context manager"
            raise RuntimeError(msg)

        discovered: list[DiscoveredDevice] = []
        found_services: list[str] = []

        def on_change(
            *,
            zeroconf: Zeroconf,  # noqa: ARG001
            service_type: str,  # noqa: ARG001
            name: str,
            state_change: ServiceStateChange,
        ) -> None:
            is_added = state_change == ServiceStateChange.Added
            is_bsblan = name.lower().startswith(BSBLAN_NAME_PREFIX)
            if is_added and is_bsblan:
                found_services.append(name)

        # Start browsing for HTTP services
        self._browser = AsyncServiceBrowser(
            self._aiozc.zeroconf,
            [BSBLAN_SERVICE_TYPE],
            handlers=[on_change],
        )

        # Wait for discovery
        await asyncio.sleep(self.discovery_seconds)

        # Resolve found services
        for service_name in found_services:
            info = AsyncServiceInfo(BSBLAN_SERVICE_TYPE, service_name)
            await info.async_request(self._aiozc.zeroconf, 3000)

            if info.addresses:
                # Get IP addresses
                addresses = [".".join(str(b) for b in addr) for addr in info.addresses]

                device = DiscoveredDevice(
                    name=service_name.replace(f".{BSBLAN_SERVICE_TYPE}", ""),
                    host=addresses[0] if addresses else "",
                    port=info.port or 80,
                    addresses=addresses,
                )
                discovered.append(device)

        self.devices = discovered
        return discovered


async def discover_bsblan(
    discovery_seconds: float = DEFAULT_DISCOVERY_SECONDS,
) -> list[DiscoveredDevice]:
    """Discover BSB-LAN devices on the network.

    Args:
        discovery_seconds: How long to wait for device discovery in seconds.

    Returns:
        List of discovered BSB-LAN devices.

    Example:
        devices = await discover_bsblan()
        for device in devices:
            print(f"Found: {device.name} at {device.host}:{device.port}")

    """
    async with BSBLANDiscovery(discovery_seconds=discovery_seconds) as discovery:
        return await discovery.discover()


async def get_first_bsblan(
    discovery_seconds: float = DEFAULT_DISCOVERY_SECONDS,
) -> DiscoveredDevice | None:
    """Get the first discovered BSB-LAN device.

    Args:
        discovery_seconds: How long to wait for device discovery in seconds.

    Returns:
        First discovered device, or None if no devices found.

    """
    devices = await discover_bsblan(discovery_seconds=discovery_seconds)
    return devices[0] if devices else None


def get_config_from_env() -> dict[str, str | int | None]:
    """Get BSB-LAN configuration from environment variables.

    Environment variables:
        BSBLAN_HOST: Device IP/hostname (optional if using discovery)
        BSBLAN_PORT: Device port (default: 80)
        BSBLAN_USER: Username for authentication
        BSBLAN_PASS: Password for authentication
        BSBLAN_PASSKEY: Passkey for authentication

    Returns:
        Dictionary with configuration values.

    """
    port_str = os.getenv(ENV_BSBLAN_PORT)
    return {
        "host": os.getenv(ENV_BSBLAN_HOST),
        "port": int(port_str) if port_str else 80,
        "username": os.getenv(ENV_BSBLAN_USER),
        "password": os.getenv(ENV_BSBLAN_PASS),
        "passkey": os.getenv(ENV_BSBLAN_PASSKEY),
    }


async def get_bsblan_host(
    discovery_seconds: float = DEFAULT_DISCOVERY_SECONDS,
    *,
    check_env_first: bool = True,
) -> tuple[str, int]:
    """Get BSB-LAN host from environment or mDNS discovery.

    Args:
        discovery_seconds: Discovery wait time in seconds.
        check_env_first: If True, check BSBLAN_HOST env var first.

    Returns:
        Tuple of (host, port).

    Raises:
        RuntimeError: If no device found and no env var set.

    """
    # Check environment first if preferred
    if check_env_first:
        env_config = get_config_from_env()
        if env_config["host"]:
            return str(env_config["host"]), int(env_config["port"] or 80)

    # Try mDNS discovery
    print("Discovering BSB-LAN devices via mDNS...")
    device = await get_first_bsblan(discovery_seconds=discovery_seconds)

    if device:
        print(f"Found: {device}")
        return device.host, device.port

    msg = (
        "No BSB-LAN device found via mDNS. "
        f"Set {ENV_BSBLAN_HOST} environment variable or check network."
    )
    raise RuntimeError(msg)


# Main function for testing discovery
async def main() -> None:
    """Test BSB-LAN discovery."""
    print("Searching for BSB-LAN devices...")
    print(f"Service type: {BSBLAN_SERVICE_TYPE}")
    print(f"Looking for names starting with: {BSBLAN_NAME_PREFIX}")
    print()

    devices = await discover_bsblan(discovery_seconds=5.0)

    if devices:
        print(f"Found {len(devices)} device(s):\n")
        for device in devices:
            print(f"  Name: {device.name}")
            print(f"  Host: {device.host}")
            print(f"  Port: {device.port}")
            print(f"  All addresses: {device.addresses}")
            print()
    else:
        print("No BSB-LAN devices found.")
        print("\nTips:")
        print("  - Make sure your BSB-LAN device is powered on")
        print("  - Check that mDNS is enabled on BSB-LAN")
        print("  - Ensure you're on the same network")
        print(f"  - Or set {ENV_BSBLAN_HOST} environment variable")


if __name__ == "__main__":
    asyncio.run(main())
