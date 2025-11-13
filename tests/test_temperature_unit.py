"""Tests for temperature unit handling in BSBLAN."""
# pylint: disable=protected-access

from unittest.mock import AsyncMock, patch

import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.models import EntityInfo, StaticState


@pytest.mark.asyncio
async def test_temperature_unit_getter() -> None:
    """Test the get_temperature_unit property."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Test default unit
    assert bsblan.get_temperature_unit == "°C"

    # Test with custom unit set
    bsblan._temperature_unit = "°F"
    assert bsblan.get_temperature_unit == "°F"


@pytest.mark.asyncio
async def test_initialize_temperature_range_celsius() -> None:
    """Test initialization of temperature range with Celsius unit."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Create mock static values with Celsius unit
    min_temp = EntityInfo(name="Min Temp", value="10", unit="°C", desc="", data_type=0)
    max_temp = EntityInfo(name="Max Temp", value="30", unit="°C", desc="", data_type=0)
    static_values = StaticState(min_temp=min_temp, max_temp=max_temp)

    # Mock static_values method to return our test data
    # Note: Temperature unit is now set during API validation, not here
    with patch.object(bsblan, "static_values", AsyncMock(return_value=static_values)):
        await bsblan._initialize_temperature_range()

        # Verify temperature range was set correctly
        assert bsblan._min_temp == 10.0
        assert bsblan._max_temp == 30.0
        assert bsblan._temperature_range_initialized is True


@pytest.mark.asyncio
async def test_initialize_temperature_range_fahrenheit() -> None:
    """Test initialization of temperature range with Fahrenheit unit."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Create mock static values with Fahrenheit unit
    min_temp = EntityInfo(name="Min Temp", value="50", unit="°F", desc="", data_type=0)
    max_temp = EntityInfo(name="Max Temp", value="86", unit="°F", desc="", data_type=0)
    static_values = StaticState(min_temp=min_temp, max_temp=max_temp)

    # Mock static_values method to return our test data
    # Note: Temperature unit is now set during API validation, not here
    with patch.object(bsblan, "static_values", AsyncMock(return_value=static_values)):
        await bsblan._initialize_temperature_range()

        # Verify temperature range was set correctly
        assert bsblan._min_temp == 50.0
        assert bsblan._max_temp == 86.0
        assert bsblan._temperature_range_initialized is True


@pytest.mark.asyncio
async def test_initialize_temperature_range_alternate_celsius_format() -> None:
    """Test initialization of temperature range with alternate Celsius format.

    Tests with HTML entity format (&deg;C) instead of unicode character.
    """
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Create mock static values with HTML degree symbol
    min_temp = EntityInfo(
        name="Min Temp", value="10", unit="&deg;C", desc="", data_type=0
    )
    max_temp = EntityInfo(
        name="Max Temp", value="30", unit="&deg;C", desc="", data_type=0
    )
    static_values = StaticState(min_temp=min_temp, max_temp=max_temp)

    # Mock static_values method to return our test data
    # Note: Temperature unit is now set during API validation, not here
    with patch.object(bsblan, "static_values", AsyncMock(return_value=static_values)):
        await bsblan._initialize_temperature_range()

        # Verify temperature range was set correctly
        assert bsblan._min_temp == 10.0
        assert bsblan._max_temp == 30.0
        assert bsblan._temperature_range_initialized is True


@pytest.mark.asyncio
async def test_extract_temperature_unit_from_response_celsius() -> None:
    """Test extracting Celsius temperature unit from heating section response."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Mock response data with parameter 710 (target_temperature) having Celsius unit
    response_data = {
        "710": {"name": "Comfort setpoint", "value": "20.0", "unit": "°C"},
        "700": {"name": "Operating mode", "value": "3", "unit": ""},
    }

    bsblan._extract_temperature_unit_from_response(response_data)

    assert bsblan._temperature_unit == "°C"


@pytest.mark.asyncio
async def test_extract_temperature_unit_from_response_fahrenheit() -> None:
    """Test extracting Fahrenheit temperature unit from heating section response."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Mock response data with parameter 710 having Fahrenheit unit
    response_data = {
        "710": {"name": "Comfort setpoint", "value": "68.0", "unit": "°F"},
        "700": {"name": "Operating mode", "value": "3", "unit": ""},
    }

    bsblan._extract_temperature_unit_from_response(response_data)

    assert bsblan._temperature_unit == "°F"


@pytest.mark.asyncio
async def test_extract_temperature_unit_from_response_html_entity() -> None:
    """Test extracting temperature unit with HTML entity format."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Mock response data with HTML entity format for Celsius
    response_data = {
        "710": {"name": "Comfort setpoint", "value": "20.0", "unit": "&deg;C"},
    }

    bsblan._extract_temperature_unit_from_response(response_data)

    assert bsblan._temperature_unit == "°C"


@pytest.mark.asyncio
async def test_extract_temperature_unit_from_response_missing_param() -> None:
    """Test behavior when parameter 710 is missing from response."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set to Fahrenheit first to verify it stays as default when param is missing
    bsblan._temperature_unit = "°F"

    # Mock response data without parameter 710
    response_data = {
        "700": {"name": "Operating mode", "value": "3", "unit": ""},
    }

    bsblan._extract_temperature_unit_from_response(response_data)

    # Should keep the existing value when param 710 is not found
    assert bsblan._temperature_unit == "°F"


@pytest.mark.asyncio
async def test_extract_temperature_unit_unknown_unit() -> None:
    """Test handling of unknown temperature unit (line 254)."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Mock response with unknown unit
    response_data = {
        "710": {
            "name": "Room Temperature",
            "value": "20.0",
            "unit": "K",  # Kelvin - unknown unit
        }
    }

    # This should log a debug message and keep default (°C)
    bsblan._extract_temperature_unit_from_response(response_data)

    # Should keep default
    assert bsblan._temperature_unit == "°C"


@pytest.mark.asyncio
async def test_extract_temperature_unit_empty_unit() -> None:
    """Test handling of empty temperature unit (line 254)."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Mock response with empty unit
    response_data = {
        "710": {
            "name": "Room Temperature",
            "value": "20.0",
            "unit": "",  # Empty unit
        }
    }

    # This should log a debug message and keep default (°C)
    bsblan._extract_temperature_unit_from_response(response_data)

    # Should keep default
    assert bsblan._temperature_unit == "°C"
