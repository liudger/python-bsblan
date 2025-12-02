"""Tests for set_hot_water_schedule method."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from bsblan.exceptions import BSBLANError
from bsblan.models import DaySchedule, DHWSchedule, TimeSlot

if TYPE_CHECKING:
    from bsblan import BSBLAN


@pytest.mark.asyncio
async def test_set_hot_water_schedule_single_day(mock_bsblan: BSBLAN) -> None:
    """Test setting hot water schedule for a single day.

    Args:
        mock_bsblan: The mock BSBLAN instance.

    """
    schedule = DHWSchedule(
        monday=DaySchedule(
            slots=[
                TimeSlot(time(6, 0), time(8, 0)),
                TimeSlot(time(17, 0), time(21, 0)),
            ]
        )
    )

    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_hot_water_schedule(schedule)

    # Verify the request was made correctly for Monday (param 561)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "561",
            "Value": "06:00-08:00 17:00-21:00",
            "Type": "1",
        },
    )


@pytest.mark.asyncio
async def test_set_hot_water_schedule_multiple_days(mock_bsblan: BSBLAN) -> None:
    """Test setting hot water schedule for multiple days.

    Args:
        mock_bsblan: The mock BSBLAN instance.

    """
    schedule = DHWSchedule(
        monday=DaySchedule(slots=[TimeSlot(time(6, 0), time(8, 0))]),
        friday=DaySchedule(slots=[TimeSlot(time(7, 0), time(9, 0))]),
    )

    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_hot_water_schedule(schedule)

    # Should have been called twice (once for Monday, once for Friday)
    assert mock_bsblan._request.await_count == 2


@pytest.mark.asyncio
async def test_set_hot_water_schedule_all_days(mock_bsblan: BSBLAN) -> None:
    """Test setting hot water schedule for all days.

    Args:
        mock_bsblan: The mock BSBLAN instance.

    """
    day = DaySchedule(slots=[TimeSlot(time(6, 0), time(8, 0))])
    schedule = DHWSchedule(
        monday=day,
        tuesday=day,
        wednesday=day,
        thursday=day,
        friday=day,
        saturday=day,
        sunday=day,
    )

    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_hot_water_schedule(schedule)

    # Should have been called 7 times (once for each day)
    assert mock_bsblan._request.await_count == 7


@pytest.mark.asyncio
async def test_set_hot_water_schedule_empty_raises_error(
    mock_bsblan: BSBLAN,
) -> None:
    """Test that empty schedule raises BSBLANError.

    Args:
        mock_bsblan: The mock BSBLAN instance.

    """
    schedule = DHWSchedule()

    with pytest.raises(BSBLANError, match="No schedule provided"):
        await mock_bsblan.set_hot_water_schedule(schedule)


@pytest.mark.asyncio
async def test_set_hot_water_schedule_parameter_ids(mock_bsblan: BSBLAN) -> None:
    """Test that correct parameter IDs are used for each day.

    Args:
        mock_bsblan: The mock BSBLAN instance.

    """
    # Expected parameter IDs for each day
    expected_params = {
        "monday": "561",
        "tuesday": "562",
        "wednesday": "563",
        "thursday": "564",
        "friday": "565",
        "saturday": "566",
        "sunday": "567",
    }

    for day_name, param_id in expected_params.items():
        # Reset mock
        assert isinstance(mock_bsblan._request, AsyncMock)
        mock_bsblan._request.reset_mock()

        # Create schedule with only this day
        schedule = DHWSchedule(
            **{day_name: DaySchedule(slots=[TimeSlot(time(6, 0), time(8, 0))])}
        )
        await mock_bsblan.set_hot_water_schedule(schedule)

        # Verify correct parameter ID was used
        call_args = mock_bsblan._request.call_args
        assert call_args is not None
        assert call_args.kwargs["data"]["Parameter"] == param_id


@pytest.mark.asyncio
async def test_set_hot_water_schedule_empty_day_schedule(
    mock_bsblan: BSBLAN,
) -> None:
    """Test setting an empty day schedule (clears the schedule).

    Args:
        mock_bsblan: The mock BSBLAN instance.

    """
    schedule = DHWSchedule(monday=DaySchedule(slots=[]))

    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_hot_water_schedule(schedule)

    # Should send empty string as value
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "561",
            "Value": "",
            "Type": "1",
        },
    )
