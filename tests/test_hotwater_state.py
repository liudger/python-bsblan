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
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("hot_water")
        bsblan._api_validator = api_validator

        # Mock the request response
        request_mock = AsyncMock(
            return_value=json.loads(load_fixture("hot_water_state.json")),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        hot_water_state: HotWaterState = await bsblan.hot_water_state()

        # Assertions
        assert isinstance(hot_water_state, HotWaterState)
        assert hot_water_state.operating_mode is not None
        assert hot_water_state.operating_mode.value == 1
        assert hot_water_state.nominal_setpoint is not None
        assert hot_water_state.nominal_setpoint.value == 50.0
        assert hot_water_state.nominal_setpoint_max is not None
        assert hot_water_state.nominal_setpoint_max.value == 65.0
        assert hot_water_state.reduced_setpoint is not None
        assert hot_water_state.reduced_setpoint.value == 10.0

        # Verify method calls
        request_mock.assert_called_once_with(
            params={
                "Parameter": (
                    "1600,1601,1610,1612,1614,1620,1630,1640,1641,1642,1644,1645,1660,1661,1663,8830,8820"
                )
            },
        )
