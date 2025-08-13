"""Tests for device time functionality."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

import json
from unittest.mock import AsyncMock

import pytest

from bsblan import BSBLAN
from bsblan.exceptions import BSBLANInvalidParameterError
from bsblan.models import DeviceTime, EntityInfo
from tests import load_fixture


@pytest.mark.asyncio
async def test_get_time(mock_bsblan: BSBLAN) -> None:
    """Test getting device time.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Load the time response from fixture
    time_response = json.loads(load_fixture("time.json"))

    assert isinstance(mock_bsblan._request, AsyncMock)
    mock_bsblan._request.return_value = time_response

    # Test getting device time
    device_time = await mock_bsblan.time()

    # Verify the request was made correctly
    mock_bsblan._request.assert_awaited_with(params={"Parameter": "0"})

    # Verify the response structure
    assert isinstance(device_time, DeviceTime)
    assert isinstance(device_time.time, EntityInfo)
    assert device_time.time.name == "Current date / Current time of day"
    assert device_time.time.value == "13.08.2025 11:51:37"
    assert device_time.time.desc == ""
    assert device_time.time.data_type == 5


@pytest.mark.asyncio
async def test_set_time(mock_bsblan: BSBLAN) -> None:
    """Test setting device time.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test setting time
    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_time("01.01.2024 12:30:45")

    # Verify the request was made correctly
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "0",
            "Value": "01.01.2024 12:30:45",
            "Type": "1",
        },
    )


@pytest.mark.asyncio
async def test_set_time_different_format(mock_bsblan: BSBLAN) -> None:
    """Test setting device time with different format.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test setting time with correct format
    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_time("13.08.2025 10:25:55")

    # Verify the request was made correctly
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "0",
            "Value": "13.08.2025 10:25:55",
            "Type": "1",
        },
    )


@pytest.mark.asyncio
async def test_set_time_invalid_formats(mock_bsblan: BSBLAN) -> None:
    """Verify that BSBLANInvalidParameterError is raised for invalid time formats.

    Verifies that BSBLANInvalidParameterError is raised for invalid time formats
    when setting device time.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test various invalid formats
    invalid_formats = [
        "2024-01-01 12:30:45",  # Wrong date separator
        "1.1.2024 12:30:45",  # Wrong day/month format (should be 2 digits)
        "01/01/2024 12:30:45",  # Wrong date separator
        "01.01.24 12:30:45",  # Wrong year format (should be 4 digits)
        "01.01.2024",  # Missing time
        "12:30:45",  # Missing date
        "01.01.2024 25:30:45",  # Invalid hour
        "01.01.2024 12:65:45",  # Invalid minute
        "01.01.2024 12:30:65",  # Invalid second
        "32.01.2024 12:30:45",  # Invalid day
        "01.13.2024 12:30:45",  # Invalid month
        "01.01.1899 12:30:45",  # Invalid year (too low)
        "01.01.2101 12:30:45",  # Invalid year (too high)
        "31.02.2024 12:30:45",  # Invalid day for February
        "31.04.2024 12:30:45",  # Invalid day for April (30 days max)
        "",  # Empty string
        "invalid format",  # Completely wrong format
    ]

    for invalid_format in invalid_formats:
        with pytest.raises(BSBLANInvalidParameterError):
            await mock_bsblan.set_time(invalid_format)


@pytest.mark.asyncio
async def test_set_time_valid_formats(mock_bsblan: BSBLAN) -> None:
    """Test that setting device time with valid formats does not raise an exception.

    Verifies that no exception is raised for valid time formats.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    assert isinstance(mock_bsblan._request, AsyncMock)

    # Test various valid formats
    valid_formats = [
        "01.01.2024 00:00:00",  # New Year
        "31.12.2024 23:59:59",  # New Year's Eve
        "29.02.2024 12:30:45",  # Leap year February 29
        "30.04.2024 15:30:45",  # April 30 (valid)
        "31.03.2024 08:15:30",  # March 31 (valid)
        "13.08.2025 10:25:55",  # The example format
    ]

    for valid_format in valid_formats:
        # Should not raise an exception
        await mock_bsblan.set_time(valid_format)


@pytest.mark.asyncio
async def test_set_time_leap_year_validation(mock_bsblan: BSBLAN) -> None:
    """Test leap year validation.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # 2024 is a leap year, so Feb 29 should be valid
    await mock_bsblan.set_time("29.02.2024 12:30:45")

    # 2023 is not a leap year, so Feb 29 should be invalid
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.set_time("29.02.2023 12:30:45")
