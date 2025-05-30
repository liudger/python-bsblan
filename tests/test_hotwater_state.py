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
from bsblan.constants import API_V3
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
        test_api_v3 = {
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

        # Mock the request response
        request_mock = AsyncMock(
            return_value=json.loads(load_fixture("hot_water_state.json")),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        hot_water_state: HotWaterState = await bsblan.hot_water_state()

        # Assertions for existing parameters
        assert isinstance(hot_water_state, HotWaterState)
        assert hot_water_state.operating_mode is not None
        assert hot_water_state.operating_mode.value == 1
        assert hot_water_state.nominal_setpoint is not None
        assert hot_water_state.nominal_setpoint.value == 50.0
        assert hot_water_state.nominal_setpoint_max is not None
        assert hot_water_state.nominal_setpoint_max.value == 65.0
        assert hot_water_state.reduced_setpoint is not None
        assert hot_water_state.reduced_setpoint.value == 10.0

        # Assertions for new parameters
        assert hot_water_state.eco_mode_selection is not None
        assert hot_water_state.eco_mode_selection.value == 0
        assert hot_water_state.dhw_charging_priority is not None
        assert hot_water_state.dhw_charging_priority.value == 0
        assert hot_water_state.legionella_dwelling_time is not None
        assert hot_water_state.legionella_dwelling_time.value == 10
        assert hot_water_state.legionella_circulation_pump is not None
        assert hot_water_state.legionella_circulation_pump.value == 0
        assert hot_water_state.legionella_circulation_temp_diff is not None
        assert hot_water_state.legionella_circulation_temp_diff.value == 5.0
        assert hot_water_state.dhw_circulation_pump_release is not None
        assert hot_water_state.dhw_circulation_pump_release.value == 1
        assert hot_water_state.dhw_circulation_pump_cycling is not None
        assert hot_water_state.dhw_circulation_pump_cycling.value == 5
        assert hot_water_state.dhw_circulation_setpoint is not None
        assert hot_water_state.dhw_circulation_setpoint.value == 45.0
        assert hot_water_state.operating_mode_changeover is not None
        assert hot_water_state.operating_mode_changeover.value == 0

        # The Parameter string in the request should include all parameters
        request_mock.assert_called_once()
        params = request_mock.call_args[1]["params"]["Parameter"].split(",")

        # Check that new parameters are included in the request
        expected_params = [
            "1600",
            "1601",
            "1610",
            "1614",
            "1612",
            "1620",
            "1630",
            "1640",
            "1645",
            "1641",
            "1642",
            "1644",
            "1646",
            "1647",
            "1648",
            "1660",
            "1661",
            "1663",
            "1680",
            "8830",
            "8820",
        ]
        for param in expected_params:
            assert param in params
