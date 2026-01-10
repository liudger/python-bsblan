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

from bsblan import BSBLAN, BSBLANConfig, State
from bsblan.constants import API_V3
from bsblan.utility import APIValidator

from . import load_fixture


@pytest.mark.asyncio
async def test_state(monkeypatch: Any) -> None:
    """Test getting BSBLAN state."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("heating")
        bsblan._api_validator = api_validator

        request_mock: AsyncMock = AsyncMock(
            return_value=json.loads(load_fixture("state.json")),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test
        state: State = await bsblan.state()

        # Basic type assertions
        assert isinstance(state, State)
        assert state is not None

        # HVAC mode assertions
        assert state.hvac_mode is not None
        assert state.hvac_mode.value == 3  # Raw integer from device
        assert state.hvac_mode.desc == "Comfort"
        assert state.hvac_mode.unit == ""

        # Target temperature assertions
        assert state.target_temperature is not None
        assert state.target_temperature.value == 18.0
        assert state.target_temperature.desc == ""
        assert state.target_temperature.unit == "°C"

    # HVAC mode changeover assertions
    assert state.hvac_mode_changeover is not None
    assert state.hvac_mode_changeover.value == 2
    assert state.hvac_mode_changeover.desc == "Reduced"

    # HVAC action assertions
    assert state.hvac_action is not None
    assert state.hvac_action.value == 122
    assert state.hvac_action.desc == "Room temperature limitation"

    # Current temperature assertions
    assert state.current_temperature is not None
    assert state.current_temperature.value == 19.3
    assert state.current_temperature.unit == "°C"

    # Room thermostat mode assertions
    assert state.room1_thermostat_mode is not None
    assert state.room1_thermostat_mode.value == 0
    assert state.room1_thermostat_mode.desc == "No demand"

    # Room temperature setpoint boost assertions
    assert state.room1_temp_setpoint_boost is not None
    assert state.room1_temp_setpoint_boost.value == "---"
    assert state.room1_temp_setpoint_boost.unit == "°C"

    # Verify API call
    request_mock.assert_called_once_with(
        params={"Parameter": "700,710,900,8000,8740,8749,770"}
    )
