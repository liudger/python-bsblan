"""Test speed comparison for BSB-LAN API calls.

Compares different approaches:
1. Multiple parallel calls (current approach)
2. Combined read_parameters call
3. With/without parameter filtering

Usage:
    # Set environment variables (optional - will use mDNS discovery if not set)
    export BSBLAN_HOST=10.0.2.60
    export BSBLAN_PORT=80
    export BSBLAN_PASSKEY=your_passkey  # if needed

    # Run the test
    python examples/speed_test.py
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bsblan import BSBLAN, BSBLANConfig
from discovery import get_bsblan_host, get_config_from_env

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

# Test configuration
NUM_WARMUP_RUNS = 2
NUM_TEST_RUNS = 10

# Parameters used in different tests
INFO_PARAMS = ["6224"]  # Current firmware version
STATIC_PARAMS = ["714", "716"]  # Min/max temp setpoints
ALL_PARAMS = INFO_PARAMS + STATIC_PARAMS

# Large parameter sets for scalability testing
# Heating parameters
HEATING_PARAMS = ["700", "710", "900", "8000", "8740", "8749"]

# Sensor parameters
SENSOR_PARAMS = ["8700", "8740"]

# Hot water parameters (a good mix of config and state)
HOT_WATER_PARAMS = [
    "1600",  # operating_mode
    "1601",  # eco_mode_selection
    "1610",  # nominal_setpoint
    "1614",  # nominal_setpoint_max
    "1612",  # reduced_setpoint
    "1620",  # release
    "1630",  # dhw_charging_priority
    "1640",  # legionella_function
    "1641",  # legionella_function_periodicity
    "1642",  # legionella_function_day
    "1644",  # legionella_function_time
    "1645",  # legionella_function_setpoint
    "8830",  # dhw_actual_value_top_temperature
    "8820",  # state_dhw_pump
]

# Combined large set (~20 params)
LARGE_PARAM_SET = HEATING_PARAMS + SENSOR_PARAMS + HOT_WATER_PARAMS[:8]  # ~16 params

# Extra large set (~22 params)
XLARGE_PARAM_SET = HEATING_PARAMS + SENSOR_PARAMS + HOT_WATER_PARAMS  # ~22 params


@dataclass
class BenchmarkResult:
    """Results from a speed benchmark."""

    name: str
    times: list[float]

    @property
    def avg(self) -> float:
        """Average time."""
        return statistics.mean(self.times)

    @property
    def min(self) -> float:
        """Minimum time."""
        return min(self.times)

    @property
    def max(self) -> float:
        """Maximum time."""
        return max(self.times)

    @property
    def median(self) -> float:
        """Median time."""
        return statistics.median(self.times)

    @property
    def stdev(self) -> float:
        """Standard deviation."""
        return statistics.stdev(self.times) if len(self.times) > 1 else 0.0

    def __str__(self) -> str:
        """Format results as string."""
        return (
            f"{self.name}:\n"
            f"  avg={self.avg:.3f}s, median={self.median:.3f}s, "
            f"min={self.min:.3f}s, max={self.max:.3f}s, stdev={self.stdev:.3f}s"
        )


async def run_test(
    name: str,
    test_fn: Callable[[], Awaitable[object]],
    num_runs: int = NUM_TEST_RUNS,
    warmup_runs: int = NUM_WARMUP_RUNS,
) -> BenchmarkResult:
    """Run a test function multiple times and collect timing stats.

    Args:
        name: Test name for display.
        test_fn: Async function to test.
        num_runs: Number of timed test runs.
        warmup_runs: Number of warmup runs (not timed).

    Returns:
        BenchmarkResult with timing statistics.

    """
    # Warmup runs (not counted)
    for _ in range(warmup_runs):
        await test_fn()

    # Timed runs
    times: list[float] = []
    for i in range(num_runs):
        start = time.perf_counter()
        await test_fn()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  Run {i + 1}/{num_runs}: {elapsed:.3f}s")

    return BenchmarkResult(name=name, times=times)


async def bench_3_parallel_calls(bsblan: BSBLAN) -> None:
    """Benchmark 3 parallel calls (current initialization approach)."""
    await asyncio.gather(
        bsblan.device(),
        bsblan.info(),
        bsblan.static_values(),
    )


async def bench_2_parallel_calls(bsblan: BSBLAN) -> None:
    """Benchmark 2 calls: device + combined read_parameters."""
    await asyncio.gather(
        bsblan.device(),
        bsblan.read_parameters(ALL_PARAMS),
    )


async def bench_1_read_params(bsblan: BSBLAN) -> None:
    """Benchmark single read_parameters call with all params."""
    await bsblan.read_parameters(ALL_PARAMS)


async def bench_static_values_filtered(bsblan: BSBLAN) -> None:
    """Benchmark static_values with include filter."""
    await bsblan.static_values(include=["min_temp"])


async def bench_info_filtered(bsblan: BSBLAN) -> None:
    """Benchmark info() with include filter."""
    await bsblan.info(include=["device_identification"])


async def bench_large_params_single_call(bsblan: BSBLAN) -> None:
    """Benchmark single call with ~16 parameters."""
    await bsblan.read_parameters(LARGE_PARAM_SET)


async def bench_xlarge_params_single_call(bsblan: BSBLAN) -> None:
    """Benchmark single call with ~22 parameters."""
    await bsblan.read_parameters(XLARGE_PARAM_SET)


async def bench_large_params_4_parallel_calls(bsblan: BSBLAN) -> None:
    """Benchmark 4 parallel calls, each with ~4 parameters."""
    chunk_size = len(LARGE_PARAM_SET) // 4
    chunks = [
        LARGE_PARAM_SET[i : i + chunk_size]
        for i in range(0, len(LARGE_PARAM_SET), chunk_size)
    ]
    await asyncio.gather(*[bsblan.read_parameters(chunk) for chunk in chunks])


async def bench_xlarge_params_4_parallel_calls(bsblan: BSBLAN) -> None:
    """Benchmark 4 parallel calls splitting ~22 parameters."""
    chunk_size = len(XLARGE_PARAM_SET) // 4
    chunks = [
        XLARGE_PARAM_SET[i : i + chunk_size]
        for i in range(0, len(XLARGE_PARAM_SET), chunk_size)
    ]
    await asyncio.gather(*[bsblan.read_parameters(chunk) for chunk in chunks])


async def bench_xlarge_params_2_parallel_calls(bsblan: BSBLAN) -> None:
    """Benchmark 2 parallel calls splitting ~22 parameters."""
    mid = len(XLARGE_PARAM_SET) // 2
    await asyncio.gather(
        bsblan.read_parameters(XLARGE_PARAM_SET[:mid]),
        bsblan.read_parameters(XLARGE_PARAM_SET[mid:]),
    )


async def bench_info_only(bsblan: BSBLAN) -> None:
    """Benchmark info() call only."""
    await bsblan.info()


async def bench_static_values_only(bsblan: BSBLAN) -> None:
    """Benchmark static_values() call only."""
    await bsblan.static_values()


async def run_all_benchmarks(bsblan: BSBLAN) -> list[BenchmarkResult]:
    """Run all speed benchmarks and return results."""
    results: list[BenchmarkResult] = []

    # Define basic tests
    basic_tests = [
        ("Test 1: 3 parallel calls (device + info + static_values)",
         "3 parallel calls", lambda: bench_3_parallel_calls(bsblan)),
        ("Test 2: 2 parallel calls (device + read_parameters)",
         "2 parallel calls", lambda: bench_2_parallel_calls(bsblan)),
        ("Test 3: Single read_parameters call",
         "1 read_parameters", lambda: bench_1_read_params(bsblan)),
        ("Test 4: static_values with include filter (min_temp only)",
         "static_values (filtered)", lambda: bench_static_values_filtered(bsblan)),
        ("Test 5: info with include filter (device_identification only)",
         "info (filtered)", lambda: bench_info_filtered(bsblan)),
        ("Test 6: static_values without filter (all params)",
         "static_values (all)", lambda: bench_static_values_only(bsblan)),
    ]

    for desc, name, bench_fn in basic_tests:
        print(f"\n{desc}")
        result = await run_test(name, bench_fn)
        results.append(result)

    # Scalability tests
    print("\n" + "=" * 60)
    print("SCALABILITY TESTS - Many Parameters")
    print("=" * 60)

    scalability_tests = [
        (f"Test 7: Single call with {len(LARGE_PARAM_SET)} params",
         f"1 call ({len(LARGE_PARAM_SET)} params)",
         lambda: bench_large_params_single_call(bsblan)),
        (f"Test 8: 4 parallel calls ({len(LARGE_PARAM_SET)} params split)",
         f"4 calls ({len(LARGE_PARAM_SET)} params)",
         lambda: bench_large_params_4_parallel_calls(bsblan)),
        (f"Test 9: Single call with {len(XLARGE_PARAM_SET)} params",
         f"1 call ({len(XLARGE_PARAM_SET)} params)",
         lambda: bench_xlarge_params_single_call(bsblan)),
        (f"Test 10: 2 parallel calls ({len(XLARGE_PARAM_SET)} params split)",
         f"2 calls ({len(XLARGE_PARAM_SET)} params)",
         lambda: bench_xlarge_params_2_parallel_calls(bsblan)),
        (f"Test 11: 4 parallel calls ({len(XLARGE_PARAM_SET)} params split)",
         f"4 calls ({len(XLARGE_PARAM_SET)} params)",
         lambda: bench_xlarge_params_4_parallel_calls(bsblan)),
    ]

    for desc, name, bench_fn in scalability_tests:
        print(f"\n{desc}")
        result = await run_test(name, bench_fn)
        results.append(result)

    return results


def print_results(results: list[BenchmarkResult]) -> None:
    """Print test results summary."""
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    for r in results:
        print(f"\n{r}")

    # Compare approaches
    baseline = results[0].avg  # 3 parallel calls
    print("\n" + "-" * 60)
    print("COMPARISON (vs 3 parallel calls baseline)")
    print("-" * 60)

    for r in results[1:]:
        diff = baseline - r.avg
        pct = (diff / baseline) * 100 if baseline > 0 else 0
        faster_slower = "faster" if diff > 0 else "slower"
        print(f"{r.name}: {abs(diff):.3f}s {faster_slower} ({abs(pct):.1f}%)")

    # Best approach
    best = min(results, key=lambda x: x.avg)
    print(f"\n✓ Best approach: {best.name} (avg: {best.avg:.3f}s)")


async def main() -> None:
    """Run speed comparison tests."""
    print("=" * 60)
    print("BSB-LAN API Speed Comparison Test")
    print("=" * 60)

    # Get configuration from environment or discovery
    env_config = get_config_from_env()

    try:
        host, port = await get_bsblan_host(discovery_seconds=3.0)
    except RuntimeError:
        print("\nNo BSB-LAN device found!")
        print("Set BSBLAN_HOST environment variable or enable mDNS on your device.")
        return

    print(f"\nConnecting to: {host}:{port}")

    # Build config
    config = BSBLANConfig(
        host=host,
        port=port,
        passkey=env_config.get("passkey") or None,
        username=env_config.get("username") or None,
        password=env_config.get("password") or None,
    )

    async with BSBLAN(config) as bsblan:
        await bsblan.initialize()
        print("✓ BSB-LAN client initialized\n")

        print(f"Running {NUM_TEST_RUNS} test runs with {NUM_WARMUP_RUNS} warmup runs\n")
        print("-" * 60)

        results = await run_all_benchmarks(bsblan)
        print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
