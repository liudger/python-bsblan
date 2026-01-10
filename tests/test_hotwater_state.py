"""Tests for retrieving hotwater information from the BSBLAN device."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

import json
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, HotWaterState
from bsblan.constants import API_V3, APIConfig
from bsblan.utility import APIValidator

from . import load_fixture


@pytest.mark.asyncio
async def test_hot_water_state(
    monkeypatch: Any,
) -> None:
    """Test getting BSBLAN hot water state."""
    # Set environment variable
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Create a modified API_V3 excluding the time switch parameters
        test_api_v3: APIConfig = {
            "heating": API_V3["heating"].copy(),
            "staticValues": API_V3["staticValues"].copy(),
            "device": API_V3["device"].copy(),
            "sensor": API_V3["sensor"].copy(),
            "hot_water": {
                k: v
                for k, v in API_V3["hot_water"].items()
                if k not in ["561", "562", "563", "564", "565", "566", "567", "576"]
            },
        }

        monkeypatch.setattr(bsblan, "_api_data", test_api_v3)

        api_validator = APIValidator(test_api_v3)
        api_validator.validated_sections.add("hot_water")
        bsblan._api_validator = api_validator

        # Set up the hot water parameter cache with all available parameters
        hot_water_cache = {
            "1600": "operating_mode",
            "1610": "nominal_setpoint",
            "1620": "release",
            "8830": "dhw_actual_value_top_temperature",
            "8820": "state_dhw_pump",
            # Add other parameters that would be in the full cache
            "1601": "eco_mode_selection",
            "1612": "reduced_setpoint",  # Now in config
            "1614": "nominal_setpoint_max",
        }
        bsblan.set_hot_water_cache(hot_water_cache)

        # Mark essential group as validated to skip validation logic
        bsblan._validated_hot_water_groups.add("essential")

        # Mock the request response to only return requested parameters
        fixture_data: dict[str, Any] = json.loads(load_fixture("hot_water_state.json"))

        def mock_request(**kwargs: Any) -> dict[str, Any]:
            # Extract requested parameter IDs from the Parameter query
            param_string = kwargs.get("params", {}).get("Parameter", "")
            if param_string:
                requested_param_ids = param_string.split(",")
                # Return only the requested parameters from the fixture
                result: dict[str, Any] = {
                    param_id: fixture_data[param_id]
                    for param_id in requested_param_ids
                    if param_id in fixture_data
                }
                return result
            return fixture_data

        request_mock = AsyncMock(side_effect=mock_request)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        hot_water_state: HotWaterState = await bsblan.hot_water_state()

        # Assertions for essential hot water state parameters only
        assert isinstance(hot_water_state, HotWaterState)
        assert hot_water_state.operating_mode is not None
        assert hot_water_state.operating_mode.value == 1
        assert hot_water_state.nominal_setpoint is not None
        assert hot_water_state.nominal_setpoint.value == 50.0
        assert hot_water_state.release is not None
        assert hot_water_state.release.value == 2
        assert hot_water_state.dhw_actual_value_top_temperature is not None
        assert hot_water_state.dhw_actual_value_top_temperature.value == 36.5
        assert hot_water_state.state_dhw_pump is not None
        assert hot_water_state.state_dhw_pump.value == 255
        # The Parameter string should only include the 5 essential parameters
        request_mock.assert_called_once()
        params = request_mock.call_args[1]["params"]["Parameter"].split(",")
        assert len(params) == 5

        expected_essential_params = [
            "1600",  # operating_mode
            "1610",  # nominal_setpoint
            "1620",  # release
            "8830",  # dhw_actual_value_top_temperature
            "8820",  # state_dhw_pump
        ]
        for param in expected_essential_params:
            assert param in params
