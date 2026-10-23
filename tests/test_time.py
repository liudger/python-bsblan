"""Tests for device time functionality."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

import json
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from bsblan import BSBLAN
from bsblan.constants import ErrorMsg
from bsblan.exceptions import BSBLANError, BSBLANInvalidParameterError
from bsblan.models import Device, DeviceTime, EntityInfo
from tests import load_fixture


def set_bsb_device_metadata(bsblan: BSBLAN) -> None:
    """Seed cached BSB device metadata for time tests."""
    bsblan._device = Device.model_validate(json.loads(load_fixture("device.json")))


def set_time_status(bsblan: BSBLAN, status: int) -> None:
    """Make BSB-LAN answer a time write with the given status."""
    assert isinstance(bsblan._request, AsyncMock)
    bsblan._request.return_value = {"0": {"status": status}}


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
    set_bsb_device_metadata(mock_bsblan)

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
    """Test setting device time."""
    set_bsb_device_metadata(mock_bsblan)
    set_time_status(mock_bsblan, 1)

    await mock_bsblan.set_time(datetime(2024, 1, 1, 12, 30, 45, tzinfo=UTC))

    assert isinstance(mock_bsblan._request, AsyncMock)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={"Parameter": "0", "Value": "01.01.2024_12:30:45", "Type": "1"},
    )


@pytest.mark.asyncio
async def test_set_time_without_timezone_conversion(mock_bsblan: BSBLAN) -> None:
    """Test the date and time are written as they are in the given timezone."""
    set_bsb_device_metadata(mock_bsblan)
    set_time_status(mock_bsblan, 1)
    utc_plus_two = timezone(timedelta(hours=2))

    await mock_bsblan.set_time(datetime(2025, 8, 13, 10, 25, 55, tzinfo=utc_plus_two))

    assert isinstance(mock_bsblan._request, AsyncMock)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={"Parameter": "0", "Value": "13.08.2025_10:25:55", "Type": "1"},
    )


@pytest.mark.asyncio
async def test_set_time_rejected(mock_bsblan: BSBLAN) -> None:
    """Test setting device time raises when BSB-LAN rejects it."""
    set_bsb_device_metadata(mock_bsblan)
    set_time_status(mock_bsblan, 0)

    with pytest.raises(BSBLANError, match=ErrorMsg.TIME_SYNC_FAILED):
        await mock_bsblan.set_time(datetime(2024, 1, 1, 12, 30, 45, tzinfo=UTC))


@pytest.mark.asyncio
@pytest.mark.parametrize("year", [1899, 2101])
async def test_set_time_invalid_year(mock_bsblan: BSBLAN, year: int) -> None:
    """Test setting device time outside the supported years raises."""
    set_bsb_device_metadata(mock_bsblan)

    with pytest.raises(BSBLANInvalidParameterError, match=f"Invalid year: {year}"):
        await mock_bsblan.set_time(datetime(year, 1, 1, 12, 30, 45, tzinfo=UTC))

    assert isinstance(mock_bsblan._request, AsyncMock)
    mock_bsblan._request.assert_not_awaited()
