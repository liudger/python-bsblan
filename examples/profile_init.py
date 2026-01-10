"""Profile BSBLAN initialization to identify performance bottlenecks.

This script profiles the initialization process of the BSBLAN library
to help identify slow operations that affect Home Assistant startup time.

Usage:
    # Basic profiling with auto-discovery or BSBLAN_HOST env var
    uv run python examples/profile_init.py

    # With explicit host
    uv run python examples/profile_init.py --host YOUR_BSBLAN_IP

    # With cProfile output
    uv run python examples/profile_init.py --cprofile

    # Save cProfile stats to file for analysis
    uv run python examples/profile_init.py --cprofile --output stats.prof
"""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import pstats
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bsblan import BSBLAN, BSBLANConfig
from bsblan.exceptions import BSBLANError
from bsblan.utility import APIValidator
from discovery import get_bsblan_host, get_config_from_env


class TimingStats:
    """Collect timing statistics for operations."""

    def __init__(self) -> None:
        """Initialize timing stats."""
        self.timings: dict[str, float] = {}
        self.start_times: dict[str, float] = {}

    def start(self, name: str) -> None:
        """Start timing an operation."""
        self.start_times[name] = time.perf_counter()

    def stop(self, name: str) -> float:
        """Stop timing and return elapsed time."""
        elapsed = time.perf_counter() - self.start_times[name]
        self.timings[name] = elapsed
        return elapsed

    @asynccontextmanager
    async def measure(self, name: str) -> AsyncIterator[None]:
        """Context manager to measure async operation time."""
        self.start(name)
        try:
            yield
        finally:
            self.stop(name)

    def report(self) -> str:
        """Generate a timing report."""
        lines = [
            "",
            "=" * 60,
            "TIMING BREAKDOWN",
            "=" * 60,
        ]

        total = sum(self.timings.values())

        # Sort by duration, longest first
        sorted_timings = sorted(self.timings.items(), key=lambda x: x[1], reverse=True)

        for name, duration in sorted_timings:
            pct = (duration / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 2)
            lines.append(f"{name:40} {duration:8.3f}s ({pct:5.1f}%) {bar}")

        lines.extend(
            [
                "-" * 60,
                f"{'TOTAL':40} {total:8.3f}s",
                "=" * 60,
            ]
        )

        return "\n".join(lines)


async def profile_detailed(
    config: BSBLANConfig,
) -> tuple[BSBLAN, TimingStats]:
    """Profile initialization with detailed timing of each step.

    This profiles the NEW lazy loading approach where sections are
    validated on-demand when first accessed.

    Note: Caller is responsible for closing client.session on success.
    """
    stats = TimingStats()

    async with stats.measure("1. Create aiohttp session"):
        session = aiohttp.ClientSession()

    client = BSBLAN(config=config, session=session)
    success = False

    try:
        # Profile lazy loading initialization (minimal upfront work)
        # Access private methods for profiling (pylint: disable=protected-access)
        async with stats.measure("2. Initialize (lazy - firmware only)"):
            # This now only fetches firmware + sets up validator
            await client.initialize()

        # Now profile what happens when we actually use sections
        # This is where lazy loading kicks in
        async with stats.measure("3. First state() call (triggers heating validation)"):
            await client.state()

        async with stats.measure("4. First sensor() call (triggers sensor validation)"):
            await client.sensor()

        async with stats.measure("5. First static_values() (triggers staticValues)"):
            await client.static_values()

        async with stats.measure("6. First hot_water_state() (triggers hot_water)"):
            await client.hot_water_state()

        success = True
        return client, stats

    finally:
        if not success:
            await session.close()


async def profile_hot_water_granular(config: BSBLANConfig) -> TimingStats:
    """Profile granular hot water parameter loading.

    This shows the benefit of only loading specific parameter groups
    (essential: 5 params, config: 16 params, schedule: 8 params)
    instead of all 29 hot water parameters at once.
    """
    stats = TimingStats()

    async with stats.measure("Create session"):
        session = aiohttp.ClientSession()

    try:
        client = BSBLAN(config=config, session=session)

        # Initialize (lazy - firmware only)
        async with stats.measure("Initialize (lazy)"):
            await client.initialize()

        # Profile each hot water method - each validates only its param group
        async with stats.measure("hot_water_state (5 essential params)"):
            await client.hot_water_state()

        async with stats.measure("hot_water_config (16 config params)"):
            await client.hot_water_config()

        async with stats.measure("hot_water_schedule (8 schedule params)"):
            await client.hot_water_schedule()

        # Second calls should be instant (already validated)
        async with stats.measure("hot_water_state (cached - no validation)"):
            await client.hot_water_state()

    finally:
        await session.close()

    return stats


async def profile_sections(config: BSBLANConfig) -> TimingStats:
    """Profile each section validation individually."""
    stats = TimingStats()

    async with stats.measure("Create session"):
        session = aiohttp.ClientSession()

    try:
        client = BSBLAN(config=config, session=session)

        # Get firmware version first (pylint: disable=protected-access)
        async with stats.measure("Fetch firmware version"):
            await client._fetch_firmware_version()  # noqa: SLF001

        # Initialize API data before validation
        client._api_data = client._copy_api_config()  # noqa: SLF001
        client._api_validator = APIValidator(client._api_data)  # noqa: SLF001

        # Profile each section individually
        sections = ["heating", "sensor", "staticValues", "device", "hot_water"]
        for section in sections:
            async with stats.measure(f"Validate section: {section}"):
                try:
                    await client._validate_api_section(section)  # type: ignore[arg-type]  # noqa: SLF001
                except BSBLANError as err:
                    print(f"Warning: Section {section} validation failed: {err}")

    finally:
        await session.close()

    return stats


async def profile_standard(config: BSBLANConfig) -> tuple[float, BSBLAN]:
    """Profile standard initialization using context manager."""
    start = time.perf_counter()

    client = BSBLAN(config=config)
    await client.__aenter__()

    elapsed = time.perf_counter() - start
    return elapsed, client


def run_cprofile(config: BSBLANConfig) -> tuple[pstats.Stats, float]:
    """Run cProfile on the initialization."""
    profiler = cProfile.Profile()

    async def _init() -> tuple[float, Any]:
        return await profile_standard(config)

    profiler.enable()
    elapsed, client = asyncio.run(_init())
    profiler.disable()

    # Cleanup
    asyncio.run(client.__aexit__(None, None, None))

    stats = pstats.Stats(profiler)
    return stats, elapsed


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Profile BSBLAN initialization performance"
    )
    parser.add_argument(
        "--host",
        help="BSBLAN device IP (uses BSBLAN_HOST env or mDNS discovery if not set)",
    )
    parser.add_argument("--port", type=int, default=80, help="BSBLAN device port")
    parser.add_argument("--username", help="Username for authentication")
    parser.add_argument("--password", help="Password for authentication")
    parser.add_argument("--passkey", help="Passkey for authentication")
    parser.add_argument(
        "--cprofile", action="store_true", help="Enable cProfile output"
    )
    parser.add_argument(
        "--output", help="Save cProfile stats to file (use with --cprofile)"
    )
    parser.add_argument(
        "--sections",
        action="store_true",
        help="Profile each section validation individually",
    )
    parser.add_argument(
        "--hot-water",
        action="store_true",
        help="Profile granular hot water parameter loading",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to repeat profiling (for averaging)",
    )
    return parser.parse_args()


def run_cprofile_mode(config: BSBLANConfig, output: str | None) -> None:
    """Run cProfile mode."""
    print("\nRunning with cProfile...")
    stats, elapsed = run_cprofile(config)

    print(f"\nTotal initialization time: {elapsed:.3f}s")
    print("\n" + "=" * 60)
    print("cProfile Results (top 30 by cumulative time):")
    print("=" * 60)

    # Print stats to stdout
    stats.sort_stats("cumulative")
    stats.print_stats(30)

    if output:
        stats.dump_stats(output)
        print(f"\nStats saved to: {output}")
        print(f"Analyze with: python -m pstats {output}")


async def run_sections_mode(config: BSBLANConfig) -> None:
    """Run sections profiling mode."""
    print("\nProfiling individual section validations...")
    stats = await profile_sections(config)
    print(stats.report())


async def run_detailed_mode(config: BSBLANConfig, repeat: int) -> None:
    """Run detailed timing mode."""
    print("\nRunning detailed timing analysis...")
    times: list[float] = []

    for i in range(repeat):
        if repeat > 1:
            print(f"\nRun {i + 1}/{repeat}")

        client, stats = await profile_detailed(config)
        times.append(sum(stats.timings.values()))

        print(stats.report())

        # Cleanup
        if client.session:
            await client.session.close()

    if repeat > 1:
        avg = sum(times) / len(times)
        min_t = min(times)
        max_t = max(times)
        print("\n" + "=" * 60)
        print("SUMMARY ACROSS RUNS")
        print("=" * 60)
        print(f"Average: {avg:.3f}s")
        print(f"Min:     {min_t:.3f}s")
        print(f"Max:     {max_t:.3f}s")


def print_recommendations() -> None:
    """Print optimization recommendations."""
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print("""
If network requests are slow:
- Check network latency to your BSB-LAN device
- Consider if some validation can be cached/skipped

If section validation is slow:
- The library validates 5 sections sequentially
- Each section requires a network round-trip
- Consider parallel validation or lazy loading

For Home Assistant specifically:
- The integration may benefit from caching device info
- Consider using config entry caching for static data
""")


async def run_hot_water_mode(config: BSBLANConfig) -> None:
    """Run hot water granular profiling mode."""
    print("\nProfiling granular hot water parameter loading...")
    print("This shows the benefit of only loading specific param groups.\n")

    stats = await profile_hot_water_granular(config)
    print(stats.report())


async def async_main() -> None:
    """Async main for profiling."""
    args = parse_args()

    # Get host from args, env, or discovery
    if args.host:
        host = args.host
        port = args.port
    else:
        host, port = await get_bsblan_host()

    # Get credentials from args or env
    env_config = get_config_from_env()
    username = args.username or env_config.get("username")
    password = args.password or env_config.get("password")
    passkey = args.passkey or env_config.get("passkey")

    config = BSBLANConfig(
        host=host,
        port=port,
        username=username,  # type: ignore[arg-type]
        password=password,  # type: ignore[arg-type]
        passkey=passkey,  # type: ignore[arg-type]
    )

    print(f"Profiling BSBLAN initialization for {host}:{port}")
    print("=" * 60)

    if args.cprofile:
        run_cprofile_mode(config, args.output)
    elif args.sections:
        await run_sections_mode(config)
    elif args.hot_water:
        await run_hot_water_mode(config)
    else:
        await run_detailed_mode(config, args.repeat)

    print_recommendations()


def main() -> None:
    """Run profiling with command line arguments."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
