"""The schedule example is read-only and validates input before discovery."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from bsblan import BSBLANConfig, ScheduleMapping, ScheduleMappings

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PROFILE = ScheduleMapping(
    monday="700",
    tuesday="700.1",
    wednesday="700.2",
    thursday="700.3",
    friday="700.4",
    saturday="700.5",
    sunday="700.6",
)
QUERY = "700,700.1,700.2,700.3,700.4,700.5,700.6"


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--heating-mapping", "{}"],
        ["--hot-water-mapping", "not-json"],
        ["--heating-mapping", PROFILE.model_dump_json(), "--circuit", "3"],
    ],
)
def test_invalid_cli_configuration_never_starts_discovery(args: list[str]) -> None:
    """The real CLI rejects absent/invalid profiles before any device contact."""
    result = subprocess.run(  # noqa: S603 - fixed executable and test inputs
        [sys.executable, str(EXAMPLES / "read_schedules.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr


def test_control_rejects_schedule_circuit_flag_before_writes() -> None:
    """--circuit can no longer select circuit 2 then write circuit 1 by default."""
    result = subprocess.run(  # noqa: S603 - fixed executable and test inputs
        [sys.executable, str(EXAMPLES / "control.py"), "--circuit", "2"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert "Setting temperature" not in result.stdout


@pytest.mark.parametrize("circuit", [1, 2])
@pytest.mark.parametrize(
    "groups", [("hot_water",), ("heating",), ("hot_water", "heating")]
)
async def test_cli_main_only_reads_configured_groups(
    aresponses: ResponsesMockServer,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    groups: tuple[str, ...],
    circuit: int,
) -> None:
    """Run the actual example and client; observe every HTTP endpoint it uses."""
    monkeypatch.syspath_prepend(str(EXAMPLES))
    example = importlib.import_module("read_schedules")
    monkeypatch.setattr(
        example, "get_bsblan_host", AsyncMock(return_value=("example.com", 80))
    )
    monkeypatch.setattr(example, "get_config_from_env", dict)
    calls = []

    async def handler(request: Any) -> Any:
        calls.append((request.path, request.query.get("Parameter")))
        if request.path == "/JI":
            body = {
                "name": "x",
                "version": "5.0.0",
                "MAC": "00:00:00:00:00:00",
                "uptime": 0,
                "bus": "BSB",
            }
        elif request.path == "/JV":
            body = {"api_version": "3.0"}
        else:
            body = {
                "700": {
                    "name": "x",
                    "value": "06:00-08:00",
                    "unit": "",
                    "desc": "",
                    "error": 0,
                    "dataType": 9,
                }
            }
        return aresponses.Response(text=json.dumps(body))

    for path in ("/JI", "/JV"):
        aresponses.add("example.com", path, "POST", handler)
    aresponses.add("example.com", "/JQ", "POST", handler, repeat=len(groups))
    args = ["--circuit", str(circuit)]
    if "hot_water" in groups:
        args.extend(["--hot-water-mapping", PROFILE.model_dump_json()])
    if "heating" in groups:
        args.extend(["--heating-mapping", PROFILE.model_dump_json()])
    await example.main(example.parse_mappings(args))
    output = capsys.readouterr().out
    assert '"raw_value": "06:00-08:00"' in output
    assert '"status": "unavailable"' in output
    assert '"retry_required": true' in output
    assert calls == [("/JI", None), ("/JV", None)] + [("/JQ", QUERY)] * len(groups)
    assert output.count('"kind": "hot_water"') == ("hot_water" in groups)
    assert output.count('"kind": "heating"') == ("heating" in groups)
    assert output.count(f'"circuit": {circuit}') == ("heating" in groups)


@pytest.mark.parametrize("configured", [False, True])
async def test_profile_example_only_reads_configured_schedules(
    aresponses: ResponsesMockServer,
    monkeypatch: pytest.MonkeyPatch,
    configured: bool,  # noqa: FBT001
) -> None:
    """Initialization profiling must still work without an implicit schedule map."""
    monkeypatch.syspath_prepend(str(EXAMPLES))
    example = importlib.import_module("profile_init")
    queries = []

    async def handler(request: Any) -> Any:
        if request.path == "/JI":
            body = {
                "name": "x",
                "version": "5.0.0",
                "MAC": "00:00:00:00:00:00",
                "uptime": 0,
                "bus": "BSB",
            }
        elif request.path == "/JV":
            body = {"api_version": "3.0"}
        else:
            params = request.query["Parameter"]
            queries.append(params)
            body = {
                p: {
                    "name": "x",
                    "value": "06:00-08:00"
                    if params == QUERY
                    else "06:00"
                    if p == "1644"
                    else "0",
                    "unit": "",
                    "desc": "",
                    "error": 0,
                    "dataType": 9 if params == QUERY else 4 if p == "1644" else 0,
                }
                for p in params.split(",")
            }
        return aresponses.Response(text=json.dumps(body))

    for path, count in (("/JI", 1), ("/JV", 1), ("/JQ", 6 if configured else 5)):
        aresponses.add("example.com", path, "POST", handler, repeat=count)
    config = BSBLANConfig(
        host="example.com",
        schedule_mappings=ScheduleMappings(hot_water=PROFILE if configured else None),
    )
    await example.profile_hot_water_granular(config)
    assert (QUERY in queries) is configured
