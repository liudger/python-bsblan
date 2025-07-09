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
    min_temp = EntityInfo(name="Min Temp", value="5", unit="°C", desc="", data_type=0)
    max_temp = EntityInfo(name="Max Temp", value="35", unit="°C", desc="", data_type=0)
    static_values = StaticState(min_temp=min_temp, max_temp=max_temp)

    # Mock static_values method to return our test data
    with patch.object(bsblan, "static_values", AsyncMock(return_value=static_values)):
        await bsblan._initialize_temperature_range()

        # Verify temperature range was set correctly
        assert bsblan._min_temp == 5.0
        assert bsblan._max_temp == 35.0
        assert bsblan._temperature_range_initialized is True
        assert bsblan._temperature_unit == "°C"


@pytest.mark.asyncio
async def test_initialize_temperature_range_fahrenheit() -> None:
    """Test initialization of temperature range with Fahrenheit unit."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Create mock static values with Fahrenheit unit
    min_temp = EntityInfo(name="Min Temp", value="41", unit="°F", desc="", data_type=0)
    max_temp = EntityInfo(name="Max Temp", value="95", unit="°F", desc="", data_type=0)
    static_values = StaticState(min_temp=min_temp, max_temp=max_temp)

    # Mock static_values method to return our test data
    with patch.object(bsblan, "static_values", AsyncMock(return_value=static_values)):
        await bsblan._initialize_temperature_range()

        # Verify temperature range was set correctly
        assert bsblan._min_temp == 41.0
        assert bsblan._max_temp == 95.0
        assert bsblan._temperature_range_initialized is True
        assert bsblan._temperature_unit == "°F"


@pytest.mark.asyncio
async def test_initialize_temperature_range_alternate_celsius_format() -> None:
    """Test initialization of temperature range with alternate Celsius format.

    Tests with HTML entity format (&deg;C) instead of unicode character.
    """
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Create mock static values with HTML degree symbol
    min_temp = EntityInfo(
        name="Min Temp", value="5", unit="&deg;C", desc="", data_type=0
    )
    max_temp = EntityInfo(
        name="Max Temp", value="35", unit="&deg;C", desc="", data_type=0
    )
    static_values = StaticState(min_temp=min_temp, max_temp=max_temp)

    # Mock static_values method to return our test data
    with patch.object(bsblan, "static_values", AsyncMock(return_value=static_values)):
        await bsblan._initialize_temperature_range()

        # Verify temperature range was set correctly
        assert bsblan._min_temp == 5.0
        assert bsblan._max_temp == 35.0
        assert bsblan._temperature_range_initialized is True
        assert bsblan._temperature_unit == "°C"
