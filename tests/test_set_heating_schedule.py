"""Tests for set_heating_schedule method."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from bsblan.exceptions import BSBLANError
from bsblan.models import DaySchedule, HeatingSchedule, TimeSlot

if TYPE_CHECKING:
    from bsblan import BSBLAN


@pytest.mark.asyncio
async def test_set_heating_schedule_circuit1_single_day(mock_bsblan: BSBLAN) -> None:
    """Test setting heating schedule for circuit 1."""
    schedule = HeatingSchedule(
        monday=DaySchedule(
            slots=[
                TimeSlot(time(6, 0), time(8, 0)),
                TimeSlot(time(17, 0), time(21, 0)),
            ]
        )
    )

    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_heating_schedule(schedule, circuit=1)

    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "501",
            "Value": "06:00-08:00 17:00-21:00",
            "Type": "1",
        },
    )


@pytest.mark.asyncio
async def test_set_heating_schedule_circuit2_single_day(mock_bsblan: BSBLAN) -> None:
    """Test setting heating schedule for circuit 2."""
    schedule = HeatingSchedule(
        monday=DaySchedule(
            slots=[
                TimeSlot(time(6, 0), time(8, 0)),
            ]
        )
    )

    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_heating_schedule(schedule, circuit=2)

    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "521",
            "Value": "06:00-08:00",
            "Type": "1",
        },
    )


@pytest.mark.asyncio
async def test_set_heating_schedule_multiple_days(mock_bsblan: BSBLAN) -> None:
    """Test setting heating schedule for multiple days."""
    schedule = HeatingSchedule(
        monday=DaySchedule(slots=[TimeSlot(time(6, 0), time(8, 0))]),
        friday=DaySchedule(slots=[TimeSlot(time(7, 0), time(9, 0))]),
    )

    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_heating_schedule(schedule, circuit=1)

    assert mock_bsblan._request.await_count == 2


@pytest.mark.asyncio
async def test_set_heating_schedule_empty_raises_error(mock_bsblan: BSBLAN) -> None:
    """Test that empty schedule raises BSBLANError."""
    schedule = HeatingSchedule()

    with pytest.raises(BSBLANError, match="No schedule provided"):
        await mock_bsblan.set_heating_schedule(schedule, circuit=1)


@pytest.mark.asyncio
async def test_set_heating_schedule_parameter_ids_per_circuit(
    mock_bsblan: BSBLAN,
) -> None:
    """Test that correct parameter IDs are used per day and circuit."""
    expected_params = {
        1: {
            "monday": "501",
            "tuesday": "502",
            "wednesday": "503",
            "thursday": "504",
            "friday": "505",
            "saturday": "506",
            "sunday": "507",
        },
        2: {
            "monday": "521",
            "tuesday": "522",
            "wednesday": "523",
            "thursday": "524",
            "friday": "525",
            "saturday": "526",
            "sunday": "527",
        },
    }

    for circuit, day_map in expected_params.items():
        for day_name, param_id in day_map.items():
            assert isinstance(mock_bsblan._request, AsyncMock)
            mock_bsblan._request.reset_mock()

            schedule = HeatingSchedule(
                **{day_name: DaySchedule(slots=[TimeSlot(time(6, 0), time(8, 0))])}
            )
            await mock_bsblan.set_heating_schedule(schedule, circuit=circuit)

            call_args = mock_bsblan._request.call_args
            assert call_args is not None
            assert call_args.kwargs["data"]["Parameter"] == param_id


@pytest.mark.asyncio
async def test_set_heating_schedule_empty_day_schedule(mock_bsblan: BSBLAN) -> None:
    """Test setting an empty day schedule (clears the schedule)."""
    schedule = HeatingSchedule(monday=DaySchedule(slots=[]))

    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_heating_schedule(schedule, circuit=1)

    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "501",
            "Value": "",
            "Type": "1",
        },
    )
