"""Tests for retrieving information from the BSBLAN device."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig, State
from bsblan.constants import API_V3  # pylint: disable=unused-import

from . import load_fixture


@pytest.mark.asyncio
async def test_state(aresponses: ResponsesMockServer, monkeypatch: Any) -> None:
    """Test getting BSBLAN state."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("state.json"),
        ),
    )
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        initialize_api_data_mock: AsyncMock = AsyncMock()
        get_parameters_mock: AsyncMock = AsyncMock(
            return_value={
                "string_par": "700,710,900,8000,8740,8749,770",
                "list": [
                    "hvac_mode",
                    "target_temperature",
                    "hvac_mode2",
                    "hvac_action",
                    "current_temperature",
                    "room1_thermostat_mode",
                    "room1_temp_setpoint_boost",
                ],
            },
        )
        request_mock: AsyncMock = AsyncMock(
            return_value=json.loads(load_fixture("state.json")),
        )

        monkeypatch.setattr(bsblan, "_initialize_api_data", initialize_api_data_mock)
        monkeypatch.setattr(bsblan, "_get_parameters", get_parameters_mock)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        state: State = await bsblan.state()

        # Assertions
        assert isinstance(state, State)
        assert state.hvac_mode.value == "heat"
        assert state.target_temperature.value == "18.0"
        assert state.current_temperature.value == "19.3"
        assert state.hvac_mode2.value == "2"
        assert state.hvac_action.value == "122"
        assert state.room1_thermostat_mode.value == "0"
        assert state.room1_temp_setpoint_boost.value == "---"

        # Verify method calls
        assert initialize_api_data_mock.call_count == 1
        assert get_parameters_mock.call_count == 1
        assert request_mock.call_count == 1
        assert request_mock.call_args[1] == {
            "params": {"Parameter": "700,710,900,8000,8740,8749,770"},
        }
