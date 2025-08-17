"""Test hot water config and schedule methods."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig
from bsblan.constants import API_V3
from bsblan.exceptions import BSBLANError
from bsblan.models import HotWaterConfig, HotWaterSchedule
from bsblan.utility import APIValidator
from tests import load_fixture


@pytest.mark.asyncio
async def test_hot_water_config(
    monkeypatch: Any,
) -> None:
    """Test getting BSBLAN hot water configuration."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("hot_water")
        bsblan._api_validator = api_validator

        # Set up the hot water parameter cache
        hot_water_cache = {
            "1601": "eco_mode_selection",
            "1614": "nominal_setpoint_max",
            "1630": "dhw_charging_priority",
            "1640": "legionella_function",
            "1645": "legionella_setpoint",
            "1660": "dhw_circulation_pump_release",
            "1661": "dhw_circulation_pump_cycling",
            "1663": "dhw_circulation_setpoint",
        }
        bsblan.set_hot_water_cache(hot_water_cache)

        # Mock the request response
        fixture_data: dict[str, Any] = json.loads(load_fixture("hot_water_state.json"))

        def mock_request(**kwargs: Any) -> dict[str, Any]:
            param_string = kwargs.get("params", {}).get("Parameter", "")
            if param_string:
                requested_param_ids = param_string.split(",")
                result: dict[str, Any] = {
                    param_id: fixture_data[param_id]
                    for param_id in requested_param_ids
                    if param_id in fixture_data
                }
                return result
            return fixture_data

        request_mock = AsyncMock(side_effect=mock_request)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        hot_water_config: HotWaterConfig = await bsblan.hot_water_config()

        # Assertions
        assert isinstance(hot_water_config, HotWaterConfig)
        # Verify that some configuration fields are present
        assert hasattr(hot_water_config, "nominal_setpoint_max")

        # The request should be called once
        request_mock.assert_called_once()


@pytest.mark.asyncio
async def test_hot_water_config_no_params_error(
    monkeypatch: Any,
) -> None:
    """Test hot water config error when no parameters available."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Create a mock API validator that returns empty parameters
        mock_validator = MagicMock()
        mock_validator.get_section_params.return_value = {}
        bsblan._api_validator = mock_validator

        # Set empty cache - no config parameters available
        bsblan.set_hot_water_cache({})

        with pytest.raises(
            BSBLANError,
            match="No hot water configuration parameters available",
        ):
            await bsblan.hot_water_config()


@pytest.mark.asyncio
async def test_hot_water_schedule(
    monkeypatch: Any,
) -> None:
    """Test getting BSBLAN hot water schedule."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("hot_water")
        bsblan._api_validator = api_validator

        # Set up the hot water parameter cache with schedule parameters
        hot_water_cache = {
            "561": "dhw_time_program_monday",
            "562": "dhw_time_program_tuesday",
            "563": "dhw_time_program_wednesday",
            "564": "dhw_time_program_thursday",
            "565": "dhw_time_program_friday",
            "566": "dhw_time_program_saturday",
            "567": "dhw_time_program_sunday",
            "576": "dhw_time_program_standard_values",
        }
        bsblan.set_hot_water_cache(hot_water_cache)

        # Create mock fixture data for schedule parameters
        schedule_fixture_data = {
            "561": {
                "name": "DHW time program Monday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Monday",
                "dataType": 0,
            },
            "562": {
                "name": "DHW time program Tuesday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Tuesday",
                "dataType": 0,
            },
            "563": {
                "name": "DHW time program Wednesday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Wednesday",
                "dataType": 0,
            },
            "564": {
                "name": "DHW time program Thursday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Thursday",
                "dataType": 0,
            },
            "565": {
                "name": "DHW time program Friday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Friday",
                "dataType": 0,
            },
            "566": {
                "name": "DHW time program Saturday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Saturday",
                "dataType": 0,
            },
            "567": {
                "name": "DHW time program Sunday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Sunday",
                "dataType": 0,
            },
            "576": {
                "name": "DHW time program standard values",
                "value": "1",
                "unit": "",
                "desc": "DHW time program standard values",
                "dataType": 0,
            },
        }

        def mock_request(**kwargs: Any) -> dict[str, Any]:
            param_string = kwargs.get("params", {}).get("Parameter", "")
            if param_string:
                requested_param_ids = param_string.split(",")
                result: dict[str, Any] = {
                    param_id: schedule_fixture_data[param_id]
                    for param_id in requested_param_ids
                    if param_id in schedule_fixture_data
                }
                return result
            return schedule_fixture_data

        request_mock = AsyncMock(side_effect=mock_request)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        hot_water_schedule: HotWaterSchedule = await bsblan.hot_water_schedule()

        # Assertions
        assert isinstance(hot_water_schedule, HotWaterSchedule)
        # Verify that some schedule fields are present
        assert hasattr(hot_water_schedule, "dhw_time_program_monday")

        # The request should be called once
        request_mock.assert_called_once()


@pytest.mark.asyncio
async def test_hot_water_schedule_no_params_error(
    monkeypatch: Any,
) -> None:
    """Test hot water schedule error when no parameters available."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Create a mock API validator that returns empty parameters
        mock_validator = MagicMock()
        mock_validator.get_section_params.return_value = {}
        bsblan._api_validator = mock_validator

        # Set empty cache - no schedule parameters available
        bsblan.set_hot_water_cache({})

        with pytest.raises(
            BSBLANError,
            match="No hot water schedule parameters available",
        ):
            await bsblan.hot_water_schedule()


@pytest.mark.asyncio
async def test_hot_water_state_no_params_error(
    monkeypatch: Any,
) -> None:
    """Test hot water state error when no essential parameters available."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Create a mock API validator that returns empty parameters
        mock_validator = MagicMock()
        mock_validator.get_section_params.return_value = {}
        bsblan._api_validator = mock_validator

        # Set empty cache - no essential parameters available
        bsblan.set_hot_water_cache({})

        with pytest.raises(
            BSBLANError,
            match="No essential hot water parameters available",
        ):
            await bsblan.hot_water_state()


@pytest.mark.asyncio
async def test_populate_hot_water_cache_no_validator() -> None:
    """Test cache population when no API validator exists."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Ensure no validator is set
    bsblan._api_validator = None  # type: ignore[assignment]

    # Should not raise an error, just return without doing anything
    bsblan._populate_hot_water_cache()

    # Cache should still be empty
    assert len(bsblan._hot_water_param_cache) == 0
