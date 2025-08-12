"""Tests for device time functionality."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from unittest.mock import AsyncMock

import pytest

from bsblan import BSBLAN
from bsblan.models import DeviceTime, EntityInfo


@pytest.mark.asyncio
async def test_get_time(mock_bsblan: BSBLAN) -> None:
    """Test getting device time.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Mock the response for parameter 0 (time)
    time_response = {
        "0": {
            "name": "Date/Time",
            "value": "01.01.2024 12:30:45",
            "unit": "",
            "desc": "Date and time",
            "dataType": 5,  # DATETIME
            "readonly": 0,
            "error": 0,
        }
    }
    
    assert isinstance(mock_bsblan._request, AsyncMock)
    mock_bsblan._request.return_value = time_response
    
    # Test getting device time
    device_time = await mock_bsblan.time()
    
    # Verify the request was made correctly
    mock_bsblan._request.assert_awaited_with(params={"Parameter": "0"})
    
    # Verify the response structure
    assert isinstance(device_time, DeviceTime)
    assert isinstance(device_time.time, EntityInfo)
    assert device_time.time.name == "Date/Time"
    assert device_time.time.value == "01.01.2024 12:30:45"
    assert device_time.time.desc == "Date and time"
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
    # Test setting time with different format
    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_time("2024-01-01 12:30:45")
    
    # Verify the request was made correctly
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "0",
            "Value": "2024-01-01 12:30:45",
            "Type": "1",
        },
    )