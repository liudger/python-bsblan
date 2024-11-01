"""Tests for retrieving information from the BSBLAN device."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

import json
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, Sensor
from bsblan.constants import API_V3
from bsblan.utility import APIValidator

from . import load_fixture


@pytest.mark.asyncio
async def test_sensor(monkeypatch: Any) -> None:
    """Test getting BSBLAN state."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("sensor")
        bsblan._api_validator = api_validator

        # Mock the request response
        request_mock = AsyncMock(
            return_value=json.loads(load_fixture("sensor.json")),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test
        sensor: Sensor = await bsblan.sensor()

        assert isinstance(sensor, Sensor)
        assert sensor is not None
        assert sensor.outside_temperature is not None
        assert sensor.outside_temperature.value == 7.6
        assert sensor.outside_temperature.unit == "&deg;C"
        assert sensor.current_temperature is not None
        assert sensor.current_temperature.value == 18.2
        assert sensor.current_temperature.unit == "&deg;C"
