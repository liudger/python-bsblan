"""Tests for the control example's structured schedule mode."""

import importlib
import json
import runpy
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

import bsblan
from bsblan import ScheduleReadMapping, ScheduleSnapshot

if TYPE_CHECKING:
    from types import ModuleType

    from bsblan import BSBLAN

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "control.py"


@pytest.fixture
def control(monkeypatch: pytest.MonkeyPatch) -> "ModuleType":
    """Import the example with its sibling discovery module available."""
    monkeypatch.syspath_prepend(str(EXAMPLE.parent))
    return importlib.import_module("examples.control")


def mapping(first: int) -> ScheduleReadMapping:
    """Build synthetic IDs, not a device mapping."""
    return ScheduleReadMapping.model_validate(
        {
            day: str(first + index)
            for index, day in enumerate(
                (
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                )
            )
        }
    )


async def test_read_structured_schedules(
    control: "ModuleType",
    mock_bsblan: "BSBLAN",
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Display actual parsed results for both configured groups."""
    request = AsyncMock(
        side_effect=[
            {
                "101": {
                    "name": "Program",
                    "value": "06:00-08:00 ##:##-##:##",
                    "unit": "",
                    "desc": "",
                    "error": 0,
                    "dataType": 9,
                }
            },
            {
                "201": {
                    "name": "Program",
                    "value": "##:##-##:##",
                    "unit": "",
                    "desc": "",
                    "error": 0,
                    "dataType": 9,
                }
            },
        ]
    )
    mock_bsblan._request = request
    await control.read_structured_schedules(mock_bsblan, mapping(101), mapping(201), 2)
    output = capsys.readouterr().out
    assert "hot_water schedule, circuit=None" in output
    assert "heating schedule, circuit=2" in output
    assert "monday: parameter=101, status=readable" in output
    assert "06:00-08:00" in output
    assert "monday: parameter=201, status=empty" in output
    assert "tuesday: parameter=102, status=unavailable" in output
    assert request.await_count == 2
    assert request.await_args_list[0].kwargs == {
        "params": {"Parameter": "101,102,103,104,105,106,107"}
    }
    assert request.await_args_list[1].kwargs == {
        "params": {"Parameter": "201,202,203,204,205,206,207"}
    }


@pytest.mark.parametrize("kind", ["hot_water", "heating"])
async def test_read_only_configured_group(
    control: "ModuleType", kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Omitting a group prevents its structured schedule request."""
    client = MagicMock()
    client.get_hot_water_schedule = AsyncMock()
    client.get_heating_schedule = AsyncMock()
    monkeypatch.setattr(control, "print_structured_schedule", MagicMock())
    configured = mapping(101)
    hot_water = configured if kind == "hot_water" else None
    heating = configured if kind == "heating" else None
    await control.read_structured_schedules(client, hot_water, heating, 2)
    if kind == "hot_water":
        client.get_hot_water_schedule.assert_awaited_once_with(mapping=configured)
        client.get_heating_schedule.assert_not_awaited()
    else:
        client.get_heating_schedule.assert_awaited_once_with(
            circuit=2, mapping=configured
        )
        client.get_hot_water_schedule.assert_not_awaited()


@pytest.mark.parametrize("kind", ["hot_water", "heating"])
async def test_structured_mode_skips_other_operations(
    control: "ModuleType",
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    """The read-only mode returns before the normal example's writes."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    reader = AsyncMock()
    monkeypatch.setattr(control, "BSBLAN", lambda _config: client)
    monkeypatch.setattr(
        control, "get_bsblan_host", AsyncMock(return_value=("example.com", 80))
    )
    monkeypatch.setattr(control, "get_config_from_env", dict)
    monkeypatch.setattr(control, "read_structured_schedules", reader)
    configured = mapping(101)
    hot_water = configured if kind == "hot_water" else None
    heating = configured if kind == "heating" else None
    await control.main(
        structured_schedules=True,
        hot_water_mapping=hot_water,
        heating_mapping=heating,
        circuit=2,
    )
    reader.assert_awaited_once_with(client, hot_water, heating, 2)
    client.thermostat.assert_not_called()
    client.set_hot_water.assert_not_called()
    client.set_time.assert_not_called()


@pytest.mark.parametrize(
    "args",
    [
        ["--structured-schedules"],
        ["--hot-water-mapping", "{}"],
        ["--structured-schedules", "--heating-mapping", "{}"],
        ["--structured-schedules", "--heating-mapping", "not-json"],
    ],
)
def test_cli_rejects_missing_or_invalid_mappings(args: list[str]) -> None:
    """Reject invalid configuration before contacting a device."""
    result = subprocess.run(  # noqa: S603 - fixed Python executable and test arguments
        [sys.executable, str(EXAMPLE), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr


def test_synthetic_mapping_is_json_serializable() -> None:
    """The CLI accepts the JSON representation documented for mappings."""
    configured = mapping(101)
    assert (
        ScheduleReadMapping.model_validate_json(json.dumps(configured.model_dump()))
        == configured
    )


def test_cli_runs_read_only_with_confirmed_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI accepts a mapping and reads it without executing write examples."""
    configured = mapping(101)
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get_hot_water_schedule = AsyncMock(
        return_value=ScheduleSnapshot(
            kind="hot_water",
            circuit=None,
            received_at=datetime.now(UTC),
            complete=False,
            days={},
        )
    )
    monkeypatch.syspath_prepend(str(EXAMPLE.parent))
    discovery = importlib.import_module("discovery")
    monkeypatch.setattr(bsblan, "BSBLAN", lambda _config: client)
    monkeypatch.setattr(
        discovery, "get_bsblan_host", AsyncMock(return_value=("example.com", 80))
    )
    monkeypatch.setattr(discovery, "get_config_from_env", dict)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(EXAMPLE),
            "--structured-schedules",
            "--hot-water-mapping",
            configured.model_dump_json(),
        ],
    )
    runpy.run_path(str(EXAMPLE), run_name="__main__")
    client.get_hot_water_schedule.assert_awaited_once_with(mapping=configured)
    client.thermostat.assert_not_called()
    client.set_hot_water.assert_not_called()
    client.set_time.assert_not_called()
