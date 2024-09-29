"""Tests for setting BSBLAN hot water state."""

import json
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig, BSBLANError
from bsblan.constants import API_V3, MULTI_PARAMETER_ERROR_MSG, NO_STATE_ERROR_MSG


@pytest.mark.asyncio
async def test_set_hot_water(aresponses: ResponsesMockServer, monkeypatch: Any) -> None:
    """Test setting BSBLAN hot water state."""
    # Set environment variable
    monkeypatch.setenv("BSBLAN_PASS", "your_password")

    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps({"status": "ok"}),
        ),
    )
    async with aiohttp.ClientSession() as session:

        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Mock _request method
        request_mock = AsyncMock(return_value={"status": "ok"})
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Test setting operating_mode
        await bsblan.set_hot_water(operating_mode="3")
        request_mock.assert_called_with(
            base_path="/JS",
            data={
                "Parameter": "1600",
                "EnumValue": "3",
                "Type": "1",
            },
        )

        # Test setting nominal_setpoint
        await bsblan.set_hot_water(nominal_setpoint=60.0)
        request_mock.assert_called_with(
            base_path="/JS",
            data={
                "Parameter": "1610",
                "Value": "60.0",
                "Type": "1",
            },
        )

        # Test setting reduced_setpoint
        await bsblan.set_hot_water(reduced_setpoint=40.0)
        request_mock.assert_called_with(
            base_path="/JS",
            data={
                "Parameter": "1612",
                "Value": "40.0",
                "Type": "1",
            },
        )

        # Test setting multiple parameters (should raise an error)
        with pytest.raises(BSBLANError, match=MULTI_PARAMETER_ERROR_MSG):
            await bsblan.set_hot_water(operating_mode="3", nominal_setpoint=60.0)


@pytest.mark.asyncio
async def test_prepare_hot_water_state() -> None:
    """Test preparing hot water state."""
    bsblan = BSBLAN(BSBLANConfig(host="example.com"))

    # Test preparing operating_mode
    state = bsblan._prepare_hot_water_state(
        operating_mode="3", nominal_setpoint=None, reduced_setpoint=None
    )
    assert state == {
        "Parameter": "1600",
        "EnumValue": "3",
        "Type": "1",
    }

    # Test preparing nominal_setpoint
    state = bsblan._prepare_hot_water_state(
        operating_mode=None, nominal_setpoint=60.0, reduced_setpoint=None
    )
    assert state == {
        "Parameter": "1610",
        "Value": "60.0",
        "Type": "1",
    }

    # Test preparing reduced_setpoint
    state = bsblan._prepare_hot_water_state(
        operating_mode=None, nominal_setpoint=None, reduced_setpoint=40.0
    )
    assert state == {
        "Parameter": "1612",
        "Value": "40.0",
        "Type": "1",
    }

    # Test preparing no parameters (should raise an error)
    with pytest.raises(BSBLANError, match=NO_STATE_ERROR_MSG):
        bsblan._prepare_hot_water_state(
            operating_mode=None, nominal_setpoint=None, reduced_setpoint=None
        )


@pytest.mark.asyncio
async def test_set_hot_water_state(
    aresponses: ResponsesMockServer, monkeypatch: Any
) -> None:
    """Test setting hot water state."""
    # Set environment variable
    monkeypatch.setenv("BSBLAN_PASS", "your_password")

    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps({"status": "ok"}),
        ),
    )
    async with aiohttp.ClientSession() as session:

        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Mock _request method
        request_mock = AsyncMock(return_value={"status": "ok"})
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Test setting hot water state
        state = {
            "Parameter": "1600",
            "EnumValue": "3",
            "Type": "1",
        }
        await bsblan._set_hot_water_state(state)
        request_mock.assert_called_with(base_path="/JS", data=state)
