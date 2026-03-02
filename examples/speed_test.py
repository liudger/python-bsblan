"""Test speed comparison for BSB-LAN API calls.

Compares different approaches using pluggable benchmark suites:
- basic: Original tests (parallel calls, read_parameters, filtering)
- scalability: Large parameter set tests
- dual-circuit: Single vs parallel calls for dual heating circuit params
- triple-circuit: Same idea extended to 3 heating circuits
- hot-water: Hot water parameter group loading tests

Usage:
    # Set environment variables (optional - will use mDNS discovery if not set)
    export BSBLAN_HOST=192.0.2.1
    export BSBLAN_PORT=80
    export BSBLAN_PASSKEY=your_passkey  # if needed

    # Run all suites
    python examples/speed_test.py

    # Run specific suite(s)
    python examples/speed_test.py --suite dual-circuit
    python examples/speed_test.py --suite basic scalability

    # Adjust run counts
    python examples/speed_test.py --runs 20 --warmup 5

    # List available suites
    python examples/speed_test.py --list-suites
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bsblan import BSBLAN, BSBLANConfig
from discovery import get_bsblan_host, get_config_from_env

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

# Default test configuration
DEFAULT_WARMUP_RUNS = 2
DEFAULT_TEST_RUNS = 10

# ---------------------------------------------------------------------------
# Parameter sets
# ---------------------------------------------------------------------------

# Info / device
INFO_PARAMS = ["6224"]  # Current firmware version
STATIC_PARAMS = ["714", "716"]  # Min/max temp setpoints
ALL_PARAMS = INFO_PARAMS + STATIC_PARAMS

# Heating circuit 1 (700-series)
HC1_PARAMS = ["700", "710", "900", "8000", "8740", "8749"]

# Heating circuit 2 (1000-series) — mirrors HC1 with offset
HC2_PARAMS = ["1000", "1010", "1200", "8001", "8741", "8750"]

# Heating circuit 3 (1300-series) — mirrors HC1 with offset
HC3_PARAMS = ["1300", "1310", "1500", "8002", "8742", "8751"]

# Static values per circuit
HC1_STATIC_PARAMS = ["714", "716"]
HC2_STATIC_PARAMS = ["1014", "1016"]
HC3_STATIC_PARAMS = ["1314", "1316"]

# Combined dual circuit parameter sets
DUAL_HEATING_PARAMS = HC1_PARAMS + HC2_PARAMS
DUAL_STATIC_PARAMS = HC1_STATIC_PARAMS + HC2_STATIC_PARAMS
DUAL_ALL_PARAMS = DUAL_HEATING_PARAMS + DUAL_STATIC_PARAMS

# Triple circuit parameter sets
TRIPLE_HEATING_PARAMS = HC1_PARAMS + HC2_PARAMS + HC3_PARAMS
TRIPLE_STATIC_PARAMS = HC1_STATIC_PARAMS + HC2_STATIC_PARAMS + HC3_STATIC_PARAMS
TRIPLE_ALL_PARAMS = TRIPLE_HEATING_PARAMS + TRIPLE_STATIC_PARAMS

# Sensor parameters
SENSOR_PARAMS = ["8700", "8740"]

# Hot water parameters
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

# Combined large set (~16 params)
LARGE_PARAM_SET = HC1_PARAMS + SENSOR_PARAMS + HOT_WATER_PARAMS[:8]

# Extra large set (~22 params)
XLARGE_PARAM_SET = HC1_PARAMS + SENSOR_PARAMS + HOT_WATER_PARAMS


# ---------------------------------------------------------------------------
# Benchmark infrastructure
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """Results from a speed benchmark."""

    name: str
    times: list[float]
    param_count: int = 0

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
        extra = f" [{self.param_count} params]" if self.param_count else ""
        return (
            f"{self.name}{extra}:\n"
            f"  avg={self.avg:.3f}s, median={self.median:.3f}s, "
            f"min={self.min:.3f}s, max={self.max:.3f}s, "
            f"stdev={self.stdev:.3f}s"
        )


@dataclass
class BenchmarkCase:
    """A single benchmark test case within a suite."""

    description: str
    short_name: str
    fn: Callable[[], Awaitable[object]]
    param_count: int = 0


@dataclass
class BenchmarkSuite:
    """A group of related benchmark test cases."""

    name: str
    description: str
    cases: list[BenchmarkCase] = field(default_factory=list)

    def add(
        self,
        description: str,
        short_name: str,
        fn: Callable[[], Awaitable[object]],
        param_count: int = 0,
    ) -> None:
        """Add a benchmark case to this suite."""
        self.cases.append(
            BenchmarkCase(
                description=description,
                short_name=short_name,
                fn=fn,
                param_count=param_count,
            )
        )


async def run_test(
    name: str,
    test_fn: Callable[[], Awaitable[object]],
    num_runs: int = DEFAULT_TEST_RUNS,
    warmup_runs: int = DEFAULT_WARMUP_RUNS,
    param_count: int = 0,
) -> BenchmarkResult:
    """Run a test function multiple times and collect timing stats.

    Args:
        name: Test name for display.
        test_fn: Async function to test.
        num_runs: Number of timed test runs.
        warmup_runs: Number of warmup runs (not timed).
        param_count: Number of parameters involved (for display).

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

    return BenchmarkResult(name=name, times=times, param_count=param_count)


async def run_suite(
    suite: BenchmarkSuite,
    num_runs: int = DEFAULT_TEST_RUNS,
    warmup_runs: int = DEFAULT_WARMUP_RUNS,
) -> list[BenchmarkResult]:
    """Run all benchmark cases in a suite.

    Args:
        suite: The benchmark suite to run.
        num_runs: Number of timed test runs per case.
        warmup_runs: Number of warmup runs per case.

    Returns:
        List of BenchmarkResult for each case.

    """
    print("\n" + "=" * 60)
    print(f"SUITE: {suite.name}")
    print(f"  {suite.description}")
    print("=" * 60)

    results: list[BenchmarkResult] = []
    for i, case in enumerate(suite.cases, 1):
        print(f"\nTest {i}: {case.description}")
        result = await run_test(
            name=case.short_name,
            test_fn=case.fn,
            num_runs=num_runs,
            warmup_runs=warmup_runs,
            param_count=case.param_count,
        )
        results.append(result)

    return results


def print_suite_results(
    suite_name: str,
    results: list[BenchmarkResult],
) -> None:
    """Print benchmark results for a suite with comparison table."""
    print("\n" + "=" * 60)
    print(f"RESULTS: {suite_name}")
    print("=" * 60)

    for r in results:
        print(f"\n{r}")

    if len(results) < 2:
        return

    # Compare against first result as baseline
    baseline = results[0]
    print("\n" + "-" * 60)
    print(f"COMPARISON (vs baseline: {baseline.name})")
    print("-" * 60)

    for r in results[1:]:
        diff = baseline.avg - r.avg
        pct = (diff / baseline.avg) * 100 if baseline.avg > 0 else 0
        faster_slower = "faster" if diff > 0 else "slower"
        print(f"{r.name}: {abs(diff):.3f}s {faster_slower} ({abs(pct):.1f}%)")

    best = min(results, key=lambda x: x.avg)
    print(f"\n✓ Best approach: {best.name} (avg: {best.avg:.3f}s)")


# ---------------------------------------------------------------------------
# Suite builders — each returns a BenchmarkSuite
# ---------------------------------------------------------------------------


def build_basic_suite(bsblan: BSBLAN) -> BenchmarkSuite:
    """Build the basic benchmark suite (original tests)."""
    suite = BenchmarkSuite(
        name="Basic",
        description=(
            "Original API call patterns: parallel calls, read_parameters, filtering"
        ),
    )

    suite.add(
        "3 parallel calls (device + info + static_values)",
        "3 parallel calls",
        lambda: asyncio.gather(
            bsblan.device(),
            bsblan.info(),
            bsblan.static_values(),
        ),
    )
    suite.add(
        "2 parallel calls (device + read_parameters)",
        "2 parallel calls",
        lambda: asyncio.gather(
            bsblan.device(),
            bsblan.read_parameters(ALL_PARAMS),
        ),
        param_count=len(ALL_PARAMS),
    )
    suite.add(
        "Single read_parameters call",
        "1 read_parameters",
        lambda: bsblan.read_parameters(ALL_PARAMS),
        param_count=len(ALL_PARAMS),
    )
    suite.add(
        "static_values with include filter (min_temp only)",
        "static_values (filtered)",
        lambda: bsblan.static_values(include=["min_temp"]),
        param_count=1,
    )
    suite.add(
        "info with include filter (device_identification only)",
        "info (filtered)",
        lambda: bsblan.info(include=["device_identification"]),
        param_count=1,
    )
    suite.add(
        "static_values without filter (all params)",
        "static_values (all)",
        bsblan.static_values,
    )

    return suite


def build_scalability_suite(bsblan: BSBLAN) -> BenchmarkSuite:
    """Build the scalability benchmark suite (many parameters)."""
    suite = BenchmarkSuite(
        name="Scalability",
        description="Testing with increasingly large parameter sets",
    )

    suite.add(
        f"Single call with {len(LARGE_PARAM_SET)} params",
        f"1 call ({len(LARGE_PARAM_SET)} params)",
        lambda: bsblan.read_parameters(LARGE_PARAM_SET),
        param_count=len(LARGE_PARAM_SET),
    )

    def _large_4_parallel() -> Awaitable[object]:
        chunk_size = max(1, len(LARGE_PARAM_SET) // 4)
        chunks = [
            LARGE_PARAM_SET[i : i + chunk_size]
            for i in range(0, len(LARGE_PARAM_SET), chunk_size)
        ]
        return asyncio.gather(*[bsblan.read_parameters(c) for c in chunks])

    suite.add(
        f"4 parallel calls ({len(LARGE_PARAM_SET)} params split)",
        f"4 calls ({len(LARGE_PARAM_SET)} params)",
        _large_4_parallel,
        param_count=len(LARGE_PARAM_SET),
    )

    suite.add(
        f"Single call with {len(XLARGE_PARAM_SET)} params",
        f"1 call ({len(XLARGE_PARAM_SET)} params)",
        lambda: bsblan.read_parameters(XLARGE_PARAM_SET),
        param_count=len(XLARGE_PARAM_SET),
    )

    def _xlarge_2_parallel() -> Awaitable[object]:
        mid = len(XLARGE_PARAM_SET) // 2
        return asyncio.gather(
            bsblan.read_parameters(XLARGE_PARAM_SET[:mid]),
            bsblan.read_parameters(XLARGE_PARAM_SET[mid:]),
        )

    suite.add(
        f"2 parallel calls ({len(XLARGE_PARAM_SET)} params split)",
        f"2 calls ({len(XLARGE_PARAM_SET)} params)",
        _xlarge_2_parallel,
        param_count=len(XLARGE_PARAM_SET),
    )

    def _xlarge_4_parallel() -> Awaitable[object]:
        chunk_size = max(1, len(XLARGE_PARAM_SET) // 4)
        chunks = [
            XLARGE_PARAM_SET[i : i + chunk_size]
            for i in range(0, len(XLARGE_PARAM_SET), chunk_size)
        ]
        return asyncio.gather(*[bsblan.read_parameters(c) for c in chunks])

    suite.add(
        f"4 parallel calls ({len(XLARGE_PARAM_SET)} params split)",
        f"4 calls ({len(XLARGE_PARAM_SET)} params)",
        _xlarge_4_parallel,
        param_count=len(XLARGE_PARAM_SET),
    )

    return suite


def build_dual_circuit_suite(bsblan: BSBLAN) -> BenchmarkSuite:
    """Build the dual heating circuit benchmark suite.

    Compares strategies for fetching parameters from two circuits:
    - 1 combined call with all HC1 + HC2 params
    - 2 parallel calls (one per circuit)
    - 2 sequential calls (one per circuit)

    NOTE: On a single-circuit system, HC2 parameters will return
    '---' or default values, but the API call overhead is the same
    — so this still measures real network timing accurately.
    """
    suite = BenchmarkSuite(
        name="Dual Heating Circuit",
        description=(
            "Compare fetching strategies for 2 heating circuits.\n"
            "  HC1 params: " + ", ".join(HC1_PARAMS) + "\n"
            "  HC2 params: " + ", ".join(HC2_PARAMS)
        ),
    )

    # --- Heating params only (state data, polled frequently) ---

    suite.add(
        f"HC1 only — 1 call ({len(HC1_PARAMS)} params)",
        f"HC1 only ({len(HC1_PARAMS)}p)",
        lambda: bsblan.read_parameters(HC1_PARAMS),
        param_count=len(HC1_PARAMS),
    )

    suite.add(
        (f"HC1+HC2 combined — 1 call ({len(DUAL_HEATING_PARAMS)} params)"),
        f"1 call ({len(DUAL_HEATING_PARAMS)}p)",
        lambda: bsblan.read_parameters(DUAL_HEATING_PARAMS),
        param_count=len(DUAL_HEATING_PARAMS),
    )

    suite.add(
        (f"HC1+HC2 parallel — 2 calls ({len(HC1_PARAMS)}+{len(HC2_PARAMS)} params)"),
        f"2 parallel ({len(HC1_PARAMS)}+{len(HC2_PARAMS)}p)",
        lambda: asyncio.gather(
            bsblan.read_parameters(HC1_PARAMS),
            bsblan.read_parameters(HC2_PARAMS),
        ),
        param_count=len(DUAL_HEATING_PARAMS),
    )

    async def _sequential_hc1_hc2() -> None:
        await bsblan.read_parameters(HC1_PARAMS)
        await bsblan.read_parameters(HC2_PARAMS)

    suite.add(
        (f"HC1+HC2 sequential — 2 calls ({len(HC1_PARAMS)}+{len(HC2_PARAMS)} params)"),
        f"2 sequential ({len(HC1_PARAMS)}+{len(HC2_PARAMS)}p)",
        _sequential_hc1_hc2,
        param_count=len(DUAL_HEATING_PARAMS),
    )

    # --- Heating + static params (full init scenario) ---

    suite.add(
        (f"HC1+HC2 all (heating+static) — 1 call ({len(DUAL_ALL_PARAMS)} params)"),
        f"1 call all ({len(DUAL_ALL_PARAMS)}p)",
        lambda: bsblan.read_parameters(DUAL_ALL_PARAMS),
        param_count=len(DUAL_ALL_PARAMS),
    )

    suite.add(
        "HC1+HC2 all — 3 parallel (heating per circuit + static)",
        "3 parallel heat+static",
        lambda: asyncio.gather(
            bsblan.read_parameters(HC1_PARAMS),
            bsblan.read_parameters(HC2_PARAMS),
            bsblan.read_parameters(DUAL_STATIC_PARAMS),
        ),
        param_count=len(DUAL_ALL_PARAMS),
    )

    suite.add(
        "HC1+HC2 all — 4 parallel (heat+static per circuit)",
        "4 parallel per section",
        lambda: asyncio.gather(
            bsblan.read_parameters(HC1_PARAMS),
            bsblan.read_parameters(HC2_PARAMS),
            bsblan.read_parameters(HC1_STATIC_PARAMS),
            bsblan.read_parameters(HC2_STATIC_PARAMS),
        ),
        param_count=len(DUAL_ALL_PARAMS),
    )

    return suite


def build_triple_circuit_suite(bsblan: BSBLAN) -> BenchmarkSuite:
    """Build the triple heating circuit benchmark suite.

    Same idea as dual-circuit but for 3 circuits. Most systems have
    at most 2 circuits; HC3 params will return '---' on those
    devices but this still measures the network call overhead.
    """
    suite = BenchmarkSuite(
        name="Triple Heating Circuit",
        description=(
            "Compare fetching strategies for 3 heating circuits.\n"
            "  HC1: " + ", ".join(HC1_PARAMS) + "\n"
            "  HC2: " + ", ".join(HC2_PARAMS) + "\n"
            "  HC3: " + ", ".join(HC3_PARAMS)
        ),
    )

    suite.add(
        (f"HC1+HC2+HC3 combined — 1 call ({len(TRIPLE_HEATING_PARAMS)} params)"),
        f"1 call ({len(TRIPLE_HEATING_PARAMS)}p)",
        lambda: bsblan.read_parameters(TRIPLE_HEATING_PARAMS),
        param_count=len(TRIPLE_HEATING_PARAMS),
    )

    suite.add(
        "HC1+HC2+HC3 parallel — 3 calls",
        "3 parallel",
        lambda: asyncio.gather(
            bsblan.read_parameters(HC1_PARAMS),
            bsblan.read_parameters(HC2_PARAMS),
            bsblan.read_parameters(HC3_PARAMS),
        ),
        param_count=len(TRIPLE_HEATING_PARAMS),
    )

    async def _sequential_3() -> None:
        await bsblan.read_parameters(HC1_PARAMS)
        await bsblan.read_parameters(HC2_PARAMS)
        await bsblan.read_parameters(HC3_PARAMS)

    suite.add(
        "HC1+HC2+HC3 sequential — 3 calls",
        "3 sequential",
        _sequential_3,
        param_count=len(TRIPLE_HEATING_PARAMS),
    )

    # Full init with static values
    suite.add(
        (f"All circuits + static — 1 call ({len(TRIPLE_ALL_PARAMS)} params)"),
        f"1 call all ({len(TRIPLE_ALL_PARAMS)}p)",
        lambda: bsblan.read_parameters(TRIPLE_ALL_PARAMS),
        param_count=len(TRIPLE_ALL_PARAMS),
    )

    suite.add(
        "All circuits + static — 6 parallel (heat+static per circ)",
        "6 parallel per section",
        lambda: asyncio.gather(
            bsblan.read_parameters(HC1_PARAMS),
            bsblan.read_parameters(HC2_PARAMS),
            bsblan.read_parameters(HC3_PARAMS),
            bsblan.read_parameters(HC1_STATIC_PARAMS),
            bsblan.read_parameters(HC2_STATIC_PARAMS),
            bsblan.read_parameters(HC3_STATIC_PARAMS),
        ),
        param_count=len(TRIPLE_ALL_PARAMS),
    )

    return suite


def build_hot_water_suite(bsblan: BSBLAN) -> BenchmarkSuite:
    """Build the hot water parameter benchmark suite."""
    suite = BenchmarkSuite(
        name="Hot Water",
        description=("Compare fetching strategies for hot water parameters"),
    )

    suite.add(
        (f"All hot water params — 1 call ({len(HOT_WATER_PARAMS)} params)"),
        f"1 call ({len(HOT_WATER_PARAMS)}p)",
        lambda: bsblan.read_parameters(HOT_WATER_PARAMS),
        param_count=len(HOT_WATER_PARAMS),
    )

    mid = len(HOT_WATER_PARAMS) // 2
    rest = len(HOT_WATER_PARAMS) - mid
    suite.add(
        f"Hot water — 2 parallel calls ({mid}+{rest})",
        "2 parallel",
        lambda: asyncio.gather(
            bsblan.read_parameters(HOT_WATER_PARAMS[:mid]),
            bsblan.read_parameters(HOT_WATER_PARAMS[mid:]),
        ),
        param_count=len(HOT_WATER_PARAMS),
    )

    # Combine hot water + dual circuit (realistic HA polling scenario)
    combined = DUAL_HEATING_PARAMS + HOT_WATER_PARAMS
    suite.add(
        (f"Dual circuit + hot water — 1 call ({len(combined)} params)"),
        f"1 call combined ({len(combined)}p)",
        lambda: bsblan.read_parameters(combined),
        param_count=len(combined),
    )

    suite.add(
        "Dual circuit + hot water — 3 parallel (HC1, HC2, DHW)",
        "3 parallel HC1+HC2+DHW",
        lambda: asyncio.gather(
            bsblan.read_parameters(HC1_PARAMS),
            bsblan.read_parameters(HC2_PARAMS),
            bsblan.read_parameters(HOT_WATER_PARAMS),
        ),
        param_count=len(combined),
    )

    return suite


# ---------------------------------------------------------------------------
# Suite registry
# ---------------------------------------------------------------------------

# Maps suite key -> builder function(bsblan) -> BenchmarkSuite
SUITE_BUILDERS: dict[str, Callable[[BSBLAN], BenchmarkSuite]] = {
    "basic": build_basic_suite,
    "scalability": build_scalability_suite,
    "dual-circuit": build_dual_circuit_suite,
    "triple-circuit": build_triple_circuit_suite,
    "hot-water": build_hot_water_suite,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="BSB-LAN API speed comparison benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Available suites:\n"
            + "\n".join(f"  {k}" for k in SUITE_BUILDERS)
            + "\n\nExamples:\n"
            "  python examples/speed_test.py --suite dual-circuit\n"
            "  python examples/speed_test.py --suite basic scalability\n"
            "  python examples/speed_test.py --runs 20 --warmup 5\n"
        ),
    )
    parser.add_argument(
        "--suite",
        nargs="+",
        choices=[*SUITE_BUILDERS, "all"],
        default=["all"],
        help="Which benchmark suite(s) to run (default: all)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_TEST_RUNS,
        help=(f"Number of timed test runs (default: {DEFAULT_TEST_RUNS})"),
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP_RUNS,
        help=(f"Number of warmup runs (default: {DEFAULT_WARMUP_RUNS})"),
    )
    parser.add_argument(
        "--list-suites",
        action="store_true",
        help="List available benchmark suites and exit",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run speed comparison benchmarks."""
    args = parse_args()

    if args.list_suites:
        print("Available benchmark suites:")
        for key in SUITE_BUILDERS:
            print(f"  {key}")
        return

    suite_keys: list[str] = (
        list(SUITE_BUILDERS.keys()) if "all" in args.suite else args.suite
    )

    print("=" * 60)
    print("BSB-LAN API Speed Comparison Benchmark")
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
    print(f"Suites: {', '.join(suite_keys)}")
    print(f"Runs: {args.runs} (warmup: {args.warmup})")

    passkey = env_config.get("passkey")
    username = env_config.get("username")
    password = env_config.get("password")

    config = BSBLANConfig(
        host=host,
        port=port,
        passkey=str(passkey) if passkey else None,
        username=str(username) if username else None,
        password=str(password) if password else None,
    )

    async with BSBLAN(config) as bsblan:
        await bsblan.initialize()
        print("✓ BSB-LAN client initialized\n")

        all_results: dict[str, list[BenchmarkResult]] = {}

        for key in suite_keys:
            builder = SUITE_BUILDERS[key]
            suite = builder(bsblan)
            results = await run_suite(
                suite,
                num_runs=args.runs,
                warmup_runs=args.warmup,
            )
            all_results[suite.name] = results
            print_suite_results(suite.name, results)

        # Print overall summary if multiple suites ran
        if len(all_results) > 1:
            print("\n" + "=" * 60)
            print("OVERALL SUMMARY")
            print("=" * 60)
            for suite_name, results in all_results.items():
                best = min(results, key=lambda x: x.avg)
                print(f"  {suite_name}: best = {best.name} ({best.avg:.3f}s)")


if __name__ == "__main__":
    asyncio.run(main())
