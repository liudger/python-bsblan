"""The control CLI is read-only unless --write opts into reversible changes."""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bsblan import (
    BSBLANError,
    DeviceTime,
    HotWaterConfig,
    HotWaterState,
    Info,
    Sensor,
)
from tests.test_control_roundtrip import (
    EXAMPLES,
    MAPPING,
    ORIGINAL,
    FakeClient,
    entity,
)

if TYPE_CHECKING:
    from datetime import datetime


@pytest.fixture
def example(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Use the real CLI and main without discovering a real gateway."""
    monkeypatch.syspath_prepend(str(EXAMPLES))
    return importlib.import_module("control")


@pytest.fixture
def configured_main(example: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Supply only mocked I/O while exercising actual printers and roundtrips."""
    client = FakeClient()
    client.json_api_version = "3.0"
    client.supports_time_sync = True
    client.info = AsyncMock(return_value=Info())
    client.sensor = AsyncMock(return_value=Sensor())
    client.hot_water_state = AsyncMock(return_value=HotWaterState())
    client.hot_water_config = AsyncMock(return_value=HotWaterConfig())
    client.time = AsyncMock(
        return_value=DeviceTime(time=entity("01.01.2026 12:00:00", dataType=7))
    )
    client.set_time = AsyncMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=context)
    monkeypatch.setattr(example, "BSBLAN", factory)
    monkeypatch.setattr(
        example, "get_bsblan_host", AsyncMock(return_value=("example.com", 80))
    )
    monkeypatch.setattr(
        example,
        "get_config_from_env",
        lambda: {"username": "u", "password": "p", "passkey": "k"},
    )
    return client, factory


def test_options_are_read_only_by_default(example: Any) -> None:
    """Invoking control.py without flags must not implicitly authorize writes."""
    options = example.parse_options([])
    assert not options.write
    assert options.temperature == 18.0
    assert options.hvac_mode == 3
    assert options.circuit == 1
    assert not options.mappings.heating
    assert options.mappings.hot_water is None


@pytest.mark.parametrize(
    "args",
    [
        ["--temperature", "nan"],
        ["--temperature", "inf"],
        ["--temperature", "bad"],
        ["--hvac-mode", "4"],
        ["--circuit", "3"],
        ["--heating-mapping", "{}"],
        ["--hot-water-mapping", "bad-json"],
        ["--schedule", "07:00-09:00"],
        ["--write", "--heating-mapping", MAPPING.model_dump_json()],
        ["--heating-mapping", MAPPING.model_dump_json(), "--schedule", "07:00-09:00"],
        [
            "--write",
            "--heating-mapping",
            MAPPING.model_dump_json(),
            "--schedule",
            "##:##-##:##",
        ],
        [
            "--write",
            "--heating-mapping",
            MAPPING.model_dump_json(),
            "--schedule",
            "bad",
        ],
        [
            "--heating-mapping",
            MAPPING.model_dump_json(),
            "--hot-water-mapping",
            MAPPING.model_dump_json(),
        ],
    ],
)
def test_invalid_options_fail_locally_before_discovery(
    example: Any, monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    """Reject malformed and potentially nonrestorable intent before any device call."""
    discovery = AsyncMock()
    monkeypatch.setattr(example, "get_bsblan_host", discovery)
    with pytest.raises(SystemExit) as err:
        example.parse_options(args)
    assert err.value.code == 2
    discovery.assert_not_awaited()


@pytest.mark.parametrize("group", ["heating", "hot_water"])
async def test_read_only_main_can_inspect_one_confirmed_schedule(
    example: Any,
    configured_main: Any,
    group: str,
) -> None:
    """No --write means no temperature, mode, schedule or clock mutation."""
    client, factory = configured_main
    flag = "--heating-mapping" if group == "heating" else "--hot-water-mapping"
    await example.main(
        example.parse_options(["--circuit", "2", flag, MAPPING.model_dump_json()])
    )
    assert all(
        name != "thermostat" and not name.startswith("set_")
        for name, _ in client.events
    )
    client.set_time.assert_not_awaited()
    assert any(name == f"{group}_schedule" for name, _ in client.events)
    config = factory.call_args.args[0]
    assert config.host == "example.com"
    assert config.username == "u"
    assert config.password == "p"  # noqa: S105 - synthetic fixture credential
    assert config.passkey == "k"
    if group == "heating":
        assert config.schedule_mappings.heating[2] == MAPPING


async def test_default_main_never_touches_schedules_or_writes(
    example: Any, configured_main: Any
) -> None:
    """The full original inspection example remains usable without a schedule map."""
    client, _ = configured_main
    await example.main(example.parse_options([]))
    assert all(
        "schedule" not in name and name != "thermostat" for name, _ in client.events
    )
    client.set_time.assert_not_awaited()


@pytest.mark.parametrize("group", ["heating", "hot_water"])
@pytest.mark.parametrize("circuit", [1, 2])
async def test_write_main_restores_controls_then_synchronizes_local_time(
    example: Any,
    configured_main: Any,
    group: str,
    circuit: int,
) -> None:
    """Time is intentionally updated, but setpoint/mode/schedule are restored."""
    client, _ = configured_main
    flag = "--heating-mapping" if group == "heating" else "--hot-water-mapping"
    options = example.parse_options(
        [
            "--write",
            "--circuit",
            str(circuit),
            flag,
            MAPPING.model_dump_json(),
            "--weekday",
            "tuesday",
            "--schedule",
            "07:00-09:00",
        ]
    )

    async def set_time(value: datetime) -> None:
        assert value.tzinfo is None
        assert client.temperature == 21
        assert client.mode == 1
        assert client.day == ORIGINAL

    client.set_time.side_effect = set_time
    await example.main(options)
    client.set_time.assert_awaited_once()
    assert client.temperature == 21
    assert client.mode == 1
    assert client.day == ORIGINAL
    assert all(
        kwargs["circuit"] == circuit
        for name, kwargs in client.events
        if name
        in {
            "state",
            "static_values",
            "thermostat",
            "heating_schedule",
            "set_heating_schedule",
        }
    )


async def test_failed_preflight_prevents_clock_sync_too(
    example: Any, configured_main: Any
) -> None:
    """Do not synchronize time or mutate anything when an original is unavailable."""
    client, _ = configured_main
    client.temperature = float("nan")
    with pytest.raises(BSBLANError):
        await example.main(example.parse_options(["--write"]))
    client.set_time.assert_not_awaited()
    assert all(name != "thermostat" for name, _ in client.events)


async def test_unsupported_time_sync_is_skipped(
    example: Any, configured_main: Any
) -> None:
    """PPS can exercise supported thermostat controls without unsupported clock I/O."""
    client, _ = configured_main
    client.supports_time_sync = False
    client.device_info = client.device_info.model_copy(update={"bus": "PPS"})
    await example.main(example.parse_options(["--write"]))
    client.time.assert_not_awaited()
    client.set_time.assert_not_awaited()
    client.hot_water_state.assert_not_awaited()
    assert client.temperature == 21
    assert client.mode == 1


async def test_optional_hot_water_configuration_failure_does_not_break_inspection(
    example: Any, configured_main: Any
) -> None:
    """Retain the original optional-configuration error handling."""
    client, _ = configured_main
    client.hot_water_config.side_effect = BSBLANError("not available")
    await example.main(example.parse_options([]))
    client.set_time.assert_not_awaited()


@pytest.mark.parametrize("group", ["heating", "hot-water"])
async def test_auto_schedule_target_needs_no_manual_mapping(
    example: Any,
    configured_main: Any,
    group: str,
) -> None:
    """Use the selected automatic API consistently without constructing overrides."""
    client, factory = configured_main
    options = example.parse_options(
        [
            "--write",
            "--schedule-group",
            group,
            "--weekday",
            "tuesday",
            "--schedule",
            "07:00-09:00",
        ]
    )
    assert options.schedule_kind == group.replace("-", "_")
    assert not options.mappings.heating
    assert options.mappings.hot_water is None
    await example.main(options)
    selected = group.replace("-", "_")
    assert any(name == f"set_{selected}_schedule" for name, _ in client.events)
    assert client.day == ORIGINAL
    assert factory.call_args.args[0].schedule_mappings == options.mappings


def test_schedule_target_defaults_to_automatic_heating(example: Any) -> None:
    """The simplest opted-in schedule command needs no mapping configuration."""
    options = example.parse_options(["--write", "--schedule", "07:00-09:00"])
    assert options.schedule_kind == "heating"
    assert not options.mappings.heating


@pytest.mark.parametrize(
    "args",
    [
        ["--write", "--schedule-group", "heating"],
        [
            "--schedule-group",
            "hot-water",
            "--heating-mapping",
            MAPPING.model_dump_json(),
        ],
        [
            "--schedule-group",
            "heating",
            "--hot-water-mapping",
            MAPPING.model_dump_json(),
        ],
    ],
)
def test_conflicting_or_incomplete_automatic_schedule_intent_fails_locally(
    example: Any,
    args: list[str],
) -> None:
    """Do not inspect one group but write or restore a different group."""
    with pytest.raises(SystemExit) as err:
        example.parse_options(args)
    assert err.value.code == 2


async def test_readonly_automatic_schedule_group_never_writes(
    example: Any,
    configured_main: Any,
) -> None:
    """Selecting automatic inspection is not write authorization."""
    client, _ = configured_main
    await example.main(example.parse_options(["--schedule-group", "heating"]))
    assert any(name == "heating_schedule" for name, _ in client.events)
    assert all(
        not name.startswith("set_") and name != "thermostat"
        for name, _ in client.events
    )
    client.set_time.assert_not_awaited()


def test_cli_help_advertises_opt_in_without_device_access() -> None:
    """Run only the safe --help path of the actual entry point."""
    result = subprocess.run(  # noqa: S603 - fixed executable and local script
        [sys.executable, str(EXAMPLES / "control.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--write" in result.stdout
    assert "--schedule" in result.stdout
