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
from bsblan.constants import API_FULL
from bsblan.utility import APIValidator

from . import load_fixture


@pytest.mark.asyncio
async def test_state(monkeypatch: Any) -> None:
    """Test getting BSBLAN state."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        monkeypatch.setattr(bsblan, "_api_data", API_FULL)

        api_validator = APIValidator(API_FULL)
        api_validator.validated_sections.add("heating")
        bsblan._validator._api_validator = api_validator

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

        # Cooling target temperature assertions
        assert state.target_temperature_high is not None
        assert state.target_temperature_high.value == 21.0
        assert state.target_temperature_high.desc == ""
        assert state.target_temperature_high.unit == "°C"

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

    # Room temperature setpoint boost assertions
    assert state.room1_temp_setpoint_boost is not None
    assert state.room1_temp_setpoint_boost.value is None
    assert state.room1_temp_setpoint_boost.unit == "°C"

    # Verify API call
    request_mock.assert_awaited_once_with(
        params={"Parameter": "700,710,900,902,8000,8740,770"}
    )


@pytest.mark.asyncio
async def test_state_with_cooling_include(monkeypatch: Any) -> None:
    """Test fetching only the cooling target temperature."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        monkeypatch.setattr(bsblan, "_api_data", API_FULL)

        api_validator = APIValidator(API_FULL)
        api_validator.validated_sections.add("heating")
        bsblan._validator._api_validator = api_validator

        state_data = json.loads(load_fixture("state.json"))
        request_mock: AsyncMock = AsyncMock(return_value={"902": state_data["902"]})
        monkeypatch.setattr(bsblan, "_request", request_mock)

        state: State = await bsblan.state(include=["target_temperature_high"])

        assert state.target_temperature_high is not None
        assert state.target_temperature_high.value == 21.0
        assert state.target_temperature is None
        request_mock.assert_awaited_once_with(params={"Parameter": "902"})


@pytest.mark.asyncio
async def test_state_without_cooling_strips_target_temperature_high(
    monkeypatch: Any,
) -> None:
    """Test unsupported cooling setpoint is stripped during validation."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        bsblan._api_data = {
            section: params.copy() for section, params in API_FULL.items()
        }
        bsblan._validator._api_validator = APIValidator(bsblan._api_data)

        state_data = json.loads(load_fixture("state.json"))
        validation_response = {"700": state_data["700"]}
        fetch_response = {"700": state_data["700"]}
        request_mock: AsyncMock = AsyncMock(
            side_effect=[validation_response, fetch_response]
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        state: State = await bsblan.state(
            include=["hvac_mode", "target_temperature_high"]
        )

        assert state.hvac_mode is not None
        assert state.target_temperature_high is None
        assert bsblan._api_data is not None
        assert "902" not in bsblan._api_data["heating"]
        assert bsblan._api_data["heating_circuit2"]["1202"] == (
            "target_temperature_high"
        )
        assert [
            call.kwargs["params"]["Parameter"] for call in request_mock.await_args_list
        ] == ["700,902", "700"]
