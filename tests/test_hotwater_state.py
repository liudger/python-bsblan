"""Tests for retrieving hotwater information from the BSBLAN device."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

import json
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig, HotWaterState
from bsblan.constants import API_V3  # Import the constant

from . import load_fixture


@pytest.mark.asyncio
async def test_hot_water_state(
    aresponses: ResponsesMockServer,
    monkeypatch: Any,
) -> None:
    """Test getting BSBLAN hot water state."""
    # Set environment variable
    monkeypatch.setenv("BSBLAN_PASS", "your_password")

    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("hot_water_state.json"),
        ),
    )
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        # set _api_version
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Use _api_data from constants.py
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Mock _initialize_api_data and _get_parameters
        # to return the specified dictionary
        initialize_api_data_mock = AsyncMock()
        get_parameters_mock = AsyncMock(
            return_value={
                "string_par": "1600,1610,1612,1620,1640,1645,1641",
                "list": [
                    "operating_mode",
                    "nominal_setpoint",
                    "reduced_setpoint",
                    "release",
                    "legionella_function",
                    "legionella_setpoint",
                    "legionella_periodically",
                ],
            },
        )
        request_mock = AsyncMock(
            return_value=json.loads(load_fixture("hot_water_state.json")),
        )

        monkeypatch.setattr(bsblan, "_initialize_api_data", initialize_api_data_mock)
        monkeypatch.setattr(bsblan, "_get_parameters", get_parameters_mock)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        hot_water_state: HotWaterState = await bsblan.hot_water_state()

        # Assertions
        assert isinstance(hot_water_state, HotWaterState)
        assert hot_water_state.operating_mode.value == "3"  # Example value
        assert hot_water_state.nominal_setpoint.value == "60.0"  # Example value
        assert hot_water_state.reduced_setpoint.value == "40.0"  # Example value
        assert hot_water_state.release.value == "1.0.0"  # Example value
        assert hot_water_state.legionella_function.value == "1"  # Example value
        assert hot_water_state.legionella_setpoint.value == "70.0"  # Example value
        assert hot_water_state.legionella_periodically.value == "1"  # Example value

        # Verify method calls
        initialize_api_data_mock.assert_called_once()
        get_parameters_mock.assert_called_once()
        request_mock.assert_called_once_with(
            params={"Parameter": "1600,1610,1612,1620,1640,1645,1641"},
        )
