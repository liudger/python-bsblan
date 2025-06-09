"""Tests for temperature push functionality."""

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import pytest
from aresponses import Response, ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig
from bsblan.exceptions import BSBLANError, BSBLANInvalidParameterError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import aiohttp

logger = logging.getLogger(__name__)


@pytest.fixture
async def mock_bsblan() -> AsyncGenerator[BSBLAN, None]:
    """Fixture to create a mocked BSBLAN instance."""
    import aiohttp

    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Mock session
    bsblan.session = aiohttp.ClientSession()

    # Mock the temperature range initialization
    bsblan._min_temp = 10.0
    bsblan._max_temp = 30.0
    bsblan._temperature_range_initialized = True
    bsblan._temperature_unit = "°C"

    try:
        yield bsblan
    finally:
        if bsblan.session:
            await bsblan.session.close()


@pytest.fixture
async def mock_aresponses() -> AsyncGenerator[ResponsesMockServer, None]:
    """Fixture to mock aiohttp responses."""
    async with ResponsesMockServer() as aresponses:
        yield aresponses


def create_response_handler(expected_data: dict[str, Any]) -> Response:
    """Create a response handler that checks the request data."""

    async def response_handler(request: aiohttp.web.Request) -> Response:
        """Check the request data."""
        assert request.method == "POST"
        assert request.host == "example.com"
        assert request.path_qs == "/JS"
        actual_data = json.loads(await request.text())

        for key, value in expected_data.items():
            assert key in actual_data, f"Expected key '{key}' not found in actual data"
            assert actual_data[key] == value, (
                f"Mismatch for key '{key}': expected {value}, "
                f"got {actual_data[key]}"
            )

        return Response(
            text=json.dumps({"status": "success"}),
            content_type="application/json",
        )

    return response_handler


@pytest.mark.asyncio
async def test_push_temperature_celsius(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test pushing room temperature in Celsius."""
    expected_data = {
        "Parameter": "10000",
        "Value": "22.5",
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.push_temperature("22.5")


@pytest.mark.asyncio
async def test_push_temperature_fahrenheit(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test pushing room temperature in Fahrenheit."""
    # Set temperature unit to Fahrenheit
    mock_bsblan._temperature_unit = "°F"
    mock_bsblan._min_temp = 50.0
    mock_bsblan._max_temp = 86.0

    expected_data = {
        "Parameter": "10000",
        "Value": "72.0",
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.push_temperature("72.0")


@pytest.mark.asyncio
async def test_push_temperature_edge_values_celsius(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test pushing edge temperature values in Celsius."""
    # Test minimum valid temperature
    expected_data_min = {
        "Parameter": "10000",
        "Value": "-50.0",
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data_min),
    )
    await mock_bsblan.push_temperature("-50.0")

    # Test maximum valid temperature
    expected_data_max = {
        "Parameter": "10000",
        "Value": "100.0",
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data_max),
    )
    await mock_bsblan.push_temperature("100.0")


@pytest.mark.asyncio
async def test_push_temperature_edge_values_fahrenheit(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test pushing edge temperature values in Fahrenheit."""
    # Set temperature unit to Fahrenheit
    mock_bsblan._temperature_unit = "°F"

    # Test minimum valid temperature
    expected_data_min = {
        "Parameter": "10000",
        "Value": "-58.0",
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data_min),
    )
    await mock_bsblan.push_temperature("-58.0")

    # Test maximum valid temperature
    expected_data_max = {
        "Parameter": "10000",
        "Value": "212.0",
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data_max),
    )
    await mock_bsblan.push_temperature("212.0")


@pytest.mark.asyncio
async def test_push_temperature_invalid_value(mock_bsblan: BSBLAN) -> None:
    """Test pushing invalid room temperature value."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("invalid")


@pytest.mark.asyncio
async def test_push_temperature_out_of_bounds_celsius(mock_bsblan: BSBLAN) -> None:
    """Test pushing temperature out of bounds in Celsius."""
    # Test below minimum
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("-51.0")

    # Test above maximum
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("101.0")


@pytest.mark.asyncio
async def test_push_temperature_out_of_bounds_fahrenheit(mock_bsblan: BSBLAN) -> None:
    """Test pushing temperature out of bounds in Fahrenheit."""
    # Set temperature unit to Fahrenheit
    mock_bsblan._temperature_unit = "°F"

    # Test below minimum
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("-59.0")

    # Test above maximum
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("213.0")


@pytest.mark.asyncio
async def test_prepare_temperature_push_state(mock_bsblan: BSBLAN) -> None:
    """Test preparing temperature push state."""
    state = mock_bsblan._prepare_temperature_push_state("25.0")

    expected_state = {
        "Parameter": "10000",
        "Value": "25.0",
        "Type": "1",
    }

    assert state == expected_state


def test_validate_room_temperature_valid_celsius(mock_bsblan: BSBLAN) -> None:
    """Test validating valid room temperature in Celsius."""
    # Should not raise exception
    mock_bsblan._validate_room_temperature("22.0")
    mock_bsblan._validate_room_temperature("0.0")
    mock_bsblan._validate_room_temperature("-10.5")
    mock_bsblan._validate_room_temperature("45.2")


def test_validate_room_temperature_valid_fahrenheit(mock_bsblan: BSBLAN) -> None:
    """Test validating valid room temperature in Fahrenheit."""
    # Set temperature unit to Fahrenheit
    mock_bsblan._temperature_unit = "°F"

    # Should not raise exception
    mock_bsblan._validate_room_temperature("72.0")
    mock_bsblan._validate_room_temperature("32.0")
    mock_bsblan._validate_room_temperature("0.0")
    mock_bsblan._validate_room_temperature("100.5")


def test_validate_room_temperature_invalid_celsius(mock_bsblan: BSBLAN) -> None:
    """Test validating invalid room temperature in Celsius."""
    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("invalid")

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("-51.0")

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("101.0")


def test_validate_room_temperature_invalid_fahrenheit(mock_bsblan: BSBLAN) -> None:
    """Test validating invalid room temperature in Fahrenheit."""
    # Set temperature unit to Fahrenheit
    mock_bsblan._temperature_unit = "°F"

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("invalid")

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("-59.0")

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("213.0")


def test_validate_room_temperature_no_range() -> None:
    """Test validating room temperature when range is not initialized."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Don't initialize temperature range
    bsblan._min_temp = None
    bsblan._max_temp = None

    with pytest.raises(BSBLANError) as exc_info:
        bsblan._validate_room_temperature("22.0")
    assert "Temperature range not initialized" in str(exc_info.value)
