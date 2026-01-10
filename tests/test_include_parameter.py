"""Tests for the include parameter in fetch methods."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, Sensor, State, StaticState
from bsblan.constants import (
    API_V3,
    INVALID_INCLUDE_PARAMS_ERROR_MSG,
)
from bsblan.exceptions import BSBLANError
from bsblan.utility import APIValidator

from . import load_fixture

if TYPE_CHECKING:
    from bsblan.models import HotWaterConfig, HotWaterSchedule, HotWaterState, Info


# ========== Tests for state() with include ==========


@pytest.mark.asyncio
async def test_state_with_include_single_param(monkeypatch: Any) -> None:
    """Test state() with a single parameter in include list."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("heating")
        bsblan._api_validator = api_validator

        # Return the hvac_mode parameter using the parameter ID as key
        # The code transforms it to use the parameter name as key
        state_data = json.loads(load_fixture("state.json"))
        partial_response = {
            "700": state_data["700"],
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with single parameter
        state: State = await bsblan.state(include=["hvac_mode"])

        # Verify only hvac_mode was requested
        request_mock.assert_awaited_once()
        call_args = request_mock.call_args
        assert "Parameter" in call_args.kwargs["params"]
        assert call_args.kwargs["params"]["Parameter"] == "700"

        # Verify hvac_mode is populated
        assert state.hvac_mode is not None
        assert state.hvac_mode.value == 3

        # Other fields should be None
        assert state.target_temperature is None


@pytest.mark.asyncio
async def test_state_with_include_multiple_params(monkeypatch: Any) -> None:
    """Test state() with multiple parameters in include list."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("heating")
        bsblan._api_validator = api_validator

        state_data = json.loads(load_fixture("state.json"))
        partial_response = {
            "700": state_data["700"],
            "8740": state_data["8740"],
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with multiple parameters
        state: State = await bsblan.state(include=["hvac_mode", "current_temperature"])

        # Verify both parameters were fetched
        assert state.hvac_mode is not None
        assert state.hvac_mode.value == 3
        assert state.current_temperature is not None
        assert state.current_temperature.value == 19.3


@pytest.mark.asyncio
async def test_state_with_include_invalid_params(monkeypatch: Any) -> None:
    """Test state() with invalid parameters in include list."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("heating")
        bsblan._api_validator = api_validator

        request_mock: AsyncMock = AsyncMock()
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with invalid parameters
        with pytest.raises(BSBLANError) as exc_info:
            await bsblan.state(include=["nonexistent_param"])

        assert str(exc_info.value) == INVALID_INCLUDE_PARAMS_ERROR_MSG
        request_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_state_without_include(monkeypatch: Any) -> None:
    """Test state() without include parameter (all params)."""
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
            return_value=json.loads(load_fixture("state.json"))
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test without include (should fetch all)
        state: State = await bsblan.state()

        # All parameters should be populated
        assert state.hvac_mode is not None
        assert state.target_temperature is not None
        assert state.current_temperature is not None


# ========== Tests for sensor() with include ==========


@pytest.mark.asyncio
async def test_sensor_with_include(monkeypatch: Any) -> None:
    """Test sensor() with include parameter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("sensor")
        bsblan._api_validator = api_validator

        partial_response = {
            "8700": json.loads(load_fixture("sensor.json"))["8700"],
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with single parameter
        sensor: Sensor = await bsblan.sensor(include=["outside_temperature"])

        # Verify only outside_temperature was requested
        request_mock.assert_awaited_once()
        call_args = request_mock.call_args
        assert call_args.kwargs["params"]["Parameter"] == "8700"

        # Verify outside_temperature is populated
        assert sensor.outside_temperature is not None


# ========== Tests for static_values() with include ==========


@pytest.mark.asyncio
async def test_static_values_with_include(monkeypatch: Any) -> None:
    """Test static_values() with include parameter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("staticValues")
        bsblan._api_validator = api_validator

        # Create a mock response with parameter ID as key
        partial_response = {
            "714": {
                "name": "Min temp",
                "unit": "°C",
                "desc": "",
                "value": "8.0",
                "dataType": 0,
                "error": 0,
                "readonly": 0,
                "readwrite": 0,
            },
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with single parameter
        static: StaticState = await bsblan.static_values(include=["min_temp"])

        # Verify min_temp is populated
        assert static.min_temp is not None
        # max_temp should be None
        assert static.max_temp is None


# ========== Tests for info() with include ==========


@pytest.mark.asyncio
async def test_info_with_include(monkeypatch: Any) -> None:
    """Test info() with include parameter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("device")
        bsblan._api_validator = api_validator

        partial_response = {
            "6224": json.loads(load_fixture("info.json"))["6224"],
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with single parameter
        info: Info = await bsblan.info(include=["device_identification"])

        # Verify device_identification is populated
        assert info.device_identification is not None
        # Other fields should be None
        assert info.controller_family is None


# ========== Tests for hot_water_state() with include ==========


@pytest.mark.asyncio
async def test_hot_water_state_with_include(monkeypatch: Any) -> None:
    """Test hot_water_state() with include parameter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Setup hot water param cache and validation
        hw_data = json.loads(load_fixture("hot_water_state.json"))
        param_cache = {
            "1600": "operating_mode",
            "1610": "nominal_setpoint",
            "1620": "release",
            "8830": "dhw_actual_value_top_temperature",
            "8820": "state_dhw_pump",
        }
        monkeypatch.setattr(bsblan, "_hot_water_param_cache", param_cache)
        bsblan._validated_hot_water_groups.add("essential")

        partial_response = {
            "1600": hw_data["1600"],
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with single parameter
        state: HotWaterState = await bsblan.hot_water_state(include=["operating_mode"])

        # Verify only operating_mode was requested
        request_mock.assert_awaited_once()
        call_args = request_mock.call_args
        assert call_args.kwargs["params"]["Parameter"] == "1600"

        # Verify operating_mode is populated
        assert state.operating_mode is not None


@pytest.mark.asyncio
async def test_hot_water_state_with_include_invalid(monkeypatch: Any) -> None:
    """Test hot_water_state() with invalid include parameter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Setup hot water param cache and validation
        param_cache = {
            "1600": "operating_mode",
            "1610": "nominal_setpoint",
        }
        monkeypatch.setattr(bsblan, "_hot_water_param_cache", param_cache)
        bsblan._validated_hot_water_groups.add("essential")

        request_mock: AsyncMock = AsyncMock()
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with invalid parameter (not in essential group)
        with pytest.raises(BSBLANError) as exc_info:
            await bsblan.hot_water_state(include=["nonexistent_param"])

        assert str(exc_info.value) == INVALID_INCLUDE_PARAMS_ERROR_MSG
        request_mock.assert_not_awaited()


# ========== Tests for hot_water_config() with include ==========


@pytest.mark.asyncio
async def test_hot_water_config_with_include(monkeypatch: Any) -> None:
    """Test hot_water_config() with include parameter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Setup hot water param cache and validation for config group
        param_cache = {
            "1601": "eco_mode_selection",
            "1614": "nominal_setpoint_max",
            "1640": "legionella_function",
            "1645": "legionella_function_setpoint",
        }
        monkeypatch.setattr(bsblan, "_hot_water_param_cache", param_cache)
        bsblan._validated_hot_water_groups.add("config")

        partial_response = {
            "1645": {
                "name": "Legionella function setpoint",
                "value": "60.0",
                "unit": "°C",
                "desc": "",
                "dataType": 0,
                "error": 0,
                "readonly": 0,
                "readwrite": 0,
            },
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with single parameter
        config_data: HotWaterConfig = await bsblan.hot_water_config(
            include=["legionella_function_setpoint"]
        )

        # Verify only legionella_function_setpoint was requested
        request_mock.assert_awaited_once()
        call_args = request_mock.call_args
        assert call_args.kwargs["params"]["Parameter"] == "1645"

        # Verify legionella_function_setpoint is populated
        assert config_data.legionella_function_setpoint is not None


# ========== Tests for hot_water_schedule() with include ==========


@pytest.mark.asyncio
async def test_hot_water_schedule_with_include(monkeypatch: Any) -> None:
    """Test hot_water_schedule() with include parameter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Setup hot water param cache and validation for schedule group
        param_cache = {
            "561": "dhw_time_program_monday",
            "562": "dhw_time_program_tuesday",
        }
        monkeypatch.setattr(bsblan, "_hot_water_param_cache", param_cache)
        bsblan._validated_hot_water_groups.add("schedule")

        partial_response = {
            "561": {
                "name": "DHW time program Monday",
                "value": "06:00-08:00 17:00-21:00",
                "unit": "",
                "desc": "",
                "dataType": 7,
                "error": 0,
                "readonly": 0,
                "readwrite": 0,
            },
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test with single parameter
        schedule: HotWaterSchedule = await bsblan.hot_water_schedule(
            include=["dhw_time_program_monday"]
        )

        # Verify only dhw_time_program_monday was requested
        request_mock.assert_awaited_once()
        call_args = request_mock.call_args
        assert call_args.kwargs["params"]["Parameter"] == "561"

        # Verify dhw_time_program_monday is populated
        assert schedule.dhw_time_program_monday is not None
