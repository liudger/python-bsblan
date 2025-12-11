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

# Sensor response with both outside_temperature and current_temperature
SENSOR_RESPONSE_FULL = json.loads(load_fixture("sensor.json"))

# Sensor response with only current_temperature (no outdoor sensor)
SENSOR_RESPONSE_NO_OUTSIDE_TEMP = {
    "8740": {
        "name": "Room temp 1 actual value",
        "error": 0,
        "value": "18.2",
        "desc": "",
        "dataType": 0,
        "readonly": 1,
        "unit": "&deg;C",
    }
}

# API config without outside_temperature parameter
API_V3_NO_OUTSIDE_TEMP = {
    **API_V3,
    "sensor": {"8740": "current_temperature"},
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("api_data", "sensor_response", "expected_outside_temp", "expected_current_temp"),
    [
        pytest.param(
            API_V3,
            SENSOR_RESPONSE_FULL,
            {"value": 7.6, "unit": "&deg;C"},
            {"value": 18.2},
            id="with_outside_temperature",
        ),
        pytest.param(
            API_V3_NO_OUTSIDE_TEMP,
            SENSOR_RESPONSE_NO_OUTSIDE_TEMP,
            None,
            {"value": 18.2},
            id="without_outside_temperature",
        ),
    ],
)
async def test_sensor(
    monkeypatch: Any,
    api_data: dict[str, Any],
    sensor_response: dict[str, Any],
    expected_outside_temp: dict[str, Any] | None,
    expected_current_temp: dict[str, Any],
) -> None:
    """Test getting BSBLAN sensor data with various configurations.

    Tests both scenarios:
    - Device with outdoor temperature sensor (parameter 8700)
    - Device without outdoor temperature sensor (outside_temperature=None)
    """
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", api_data)

        api_validator = APIValidator(api_data)
        api_validator.validated_sections.add("sensor")
        bsblan._api_validator = api_validator

        request_mock = AsyncMock(return_value=sensor_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Execute test
        sensor: Sensor = await bsblan.sensor()

        # Verify sensor model
        assert isinstance(sensor, Sensor)

        if expected_outside_temp is None:
            assert sensor.outside_temperature is None
        else:
            assert sensor.outside_temperature is not None
            assert sensor.outside_temperature.value == expected_outside_temp["value"]
            assert sensor.outside_temperature.unit == expected_outside_temp["unit"]

        assert sensor.current_temperature is not None
        assert sensor.current_temperature.value == expected_current_temp["value"]
        assert sensor.current_temperature.value == 18.2
        assert sensor.current_temperature.unit == "&deg;C"
