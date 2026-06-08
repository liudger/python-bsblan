"""Tests for retrieving information from the BSBLAN device."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

import json
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, StaticState
from bsblan.constants import API_V3
from bsblan.utility import APIValidator

from . import load_fixture


@pytest.mark.asyncio
async def test_sensor(monkeypatch: Any) -> None:
    """Test getting BSBLAN state."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(config=BSBLANConfig(host="example.com"), session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("staticValues")
        bsblan._validator._api_validator = api_validator

        # Mock the request response
        request_mock = AsyncMock(
            return_value=json.loads(load_fixture("static_state.json")),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        static: StaticState = await bsblan.static_values()
        assert isinstance(static, StaticState)
        assert static.temp_reduced_setpoint is not None
        assert static.temp_reduced_setpoint.value == 17.0
        assert static.min_temp is None
        assert static.comfort_setpoint_max is not None
        assert static.comfort_setpoint_max.value == 23.0
        assert static.heating_protective_setpoint is not None
        assert static.heating_protective_setpoint.value == 8.0
        assert static.cooling_comfort_setpoint_min is not None
        assert static.cooling_comfort_setpoint_min.value == 18.0
        assert static.cooling_reduced_setpoint is not None
        assert static.cooling_reduced_setpoint.value == 26.0
