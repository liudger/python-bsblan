"""Tests for temperature push functionality."""

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

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


def create_inf_telegram_response_handler(
    expected_param: str, expected_value: str
) -> Response:
    """Create a response handler for INF telegram requests."""

    async def response_handler(request: aiohttp.web.Request) -> Response:
        """Check the INF telegram request."""
        assert request.method == "GET"
        assert request.host == "example.com"
        expected_path = f"/I{expected_param}={expected_value}"
        assert request.path_qs == expected_path, (
            f"Expected path '{expected_path}', got '{request.path_qs}'"
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
    mock_aresponses.add(
        "example.com",
        "/I10000=22.5",
        "GET",
        create_inf_telegram_response_handler("10000", "22.5"),
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
    mock_bsblan._min_temp = 41.0
    mock_bsblan._max_temp = 95.0

    mock_aresponses.add(
        "example.com",
        "/I10000=72.0",
        "GET",
        create_inf_telegram_response_handler("10000", "72.0"),
    )
    await mock_bsblan.push_temperature("72.0")


@pytest.mark.asyncio
async def test_push_temperature_edge_values_celsius(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test pushing edge temperature values in Celsius."""
    # Test minimum valid temperature (-10°C)
    mock_aresponses.add(
        "example.com",
        "/I10000=-10.0",
        "GET",
        create_inf_telegram_response_handler("10000", "-10.0"),
    )
    await mock_bsblan.push_temperature("-10.0")

    # Test maximum valid temperature (50°C)
    mock_aresponses.add(
        "example.com",
        "/I10000=50.0",
        "GET",
        create_inf_telegram_response_handler("10000", "50.0"),
    )
    await mock_bsblan.push_temperature("50.0")


@pytest.mark.asyncio
async def test_push_temperature_edge_values_fahrenheit(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test pushing edge temperature values in Fahrenheit."""
    # Set temperature unit to Fahrenheit
    mock_bsblan._temperature_unit = "°F"

    # Test minimum valid temperature (14°F)
    mock_aresponses.add(
        "example.com",
        "/I10000=14.0",
        "GET",
        create_inf_telegram_response_handler("10000", "14.0"),
    )
    await mock_bsblan.push_temperature("14.0")

    # Test maximum valid temperature (122°F)
    mock_aresponses.add(
        "example.com",
        "/I10000=122.0",
        "GET",
        create_inf_telegram_response_handler("10000", "122.0"),
    )
    await mock_bsblan.push_temperature("122.0")


@pytest.mark.asyncio
async def test_push_temperature_invalid_value(mock_bsblan: BSBLAN) -> None:
    """Test pushing invalid room temperature value."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("invalid")


@pytest.mark.asyncio
async def test_push_temperature_out_of_bounds_celsius(mock_bsblan: BSBLAN) -> None:
    """Test pushing temperature out of bounds in Celsius."""
    # Test below minimum (-10°C)
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("-11.0")

    # Test above maximum (50°C)
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("51.0")


@pytest.mark.asyncio
async def test_push_temperature_out_of_bounds_fahrenheit(mock_bsblan: BSBLAN) -> None:
    """Test pushing temperature out of bounds in Fahrenheit."""
    # Set temperature unit to Fahrenheit
    mock_bsblan._temperature_unit = "°F"

    # Test below minimum (14°F)
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("13.0")

    # Test above maximum (122°F)
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.push_temperature("123.0")


def test_validate_room_temperature_valid_celsius(mock_bsblan: BSBLAN) -> None:
    """Test validating valid room temperature in Celsius."""
    # Should not raise exception
    mock_bsblan._validate_room_temperature("22.0")
    mock_bsblan._validate_room_temperature("0.0")
    mock_bsblan._validate_room_temperature("-5.0")
    mock_bsblan._validate_room_temperature("45.0")


def test_validate_room_temperature_valid_fahrenheit(mock_bsblan: BSBLAN) -> None:
    """Test validating valid room temperature in Fahrenheit."""
    # Set temperature unit to Fahrenheit
    mock_bsblan._temperature_unit = "°F"

    # Should not raise exception
    mock_bsblan._validate_room_temperature("72.0")
    mock_bsblan._validate_room_temperature("32.0")
    mock_bsblan._validate_room_temperature("20.0")
    mock_bsblan._validate_room_temperature("100.0")


def test_validate_room_temperature_invalid_celsius(mock_bsblan: BSBLAN) -> None:
    """Test validating invalid room temperature in Celsius."""
    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("invalid")

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("-11.0")

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("51.0")


def test_validate_room_temperature_invalid_fahrenheit(mock_bsblan: BSBLAN) -> None:
    """Test validating invalid room temperature in Fahrenheit."""
    # Set temperature unit to Fahrenheit
    mock_bsblan._temperature_unit = "°F"

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("invalid")

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("13.0")

    with pytest.raises(BSBLANInvalidParameterError):
        mock_bsblan._validate_room_temperature("123.0")


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
