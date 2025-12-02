"""Test cases for schedule models (TimeSlot, DaySchedule, DHWSchedule)."""

from __future__ import annotations

from datetime import time

import pytest

from bsblan.models import DaySchedule, DHWSchedule, TimeSlot


class TestTimeSlot:
    """Test cases for TimeSlot dataclass."""

    def test_valid_time_slot(self) -> None:
        """Test creating a valid time slot."""
        slot = TimeSlot(start=time(6, 0), end=time(8, 0))
        assert slot.start == time(6, 0)
        assert slot.end == time(8, 0)

    def test_time_slot_to_bsblan_format(self) -> None:
        """Test converting time slot to BSB-LAN format."""
        slot = TimeSlot(start=time(6, 0), end=time(8, 0))
        assert slot.to_bsblan_format() == "06:00-08:00"

    def test_time_slot_to_bsblan_format_with_minutes(self) -> None:
        """Test converting time slot with non-zero minutes."""
        slot = TimeSlot(start=time(6, 30), end=time(8, 45))
        assert slot.to_bsblan_format() == "06:30-08:45"

    def test_time_slot_from_bsblan_format(self) -> None:
        """Test parsing time slot from BSB-LAN format."""
        slot = TimeSlot.from_bsblan_format("06:00-08:00")
        assert slot.start == time(6, 0)
        assert slot.end == time(8, 0)

    def test_time_slot_from_bsblan_format_with_minutes(self) -> None:
        """Test parsing time slot with non-zero minutes."""
        slot = TimeSlot.from_bsblan_format("17:30-21:45")
        assert slot.start == time(17, 30)
        assert slot.end == time(21, 45)

    def test_time_slot_invalid_start_after_end(self) -> None:
        """Test that start time must be before end time."""
        with pytest.raises(ValueError, match="must be before end time"):
            TimeSlot(start=time(10, 0), end=time(8, 0))

    def test_time_slot_invalid_start_equals_end(self) -> None:
        """Test that start time cannot equal end time."""
        with pytest.raises(ValueError, match="must be before end time"):
            TimeSlot(start=time(8, 0), end=time(8, 0))

    def test_time_slot_from_invalid_format(self) -> None:
        """Test parsing invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid time slot format"):
            TimeSlot.from_bsblan_format("invalid")

    def test_time_slot_from_invalid_format_missing_dash(self) -> None:
        """Test parsing format without dash raises ValueError."""
        with pytest.raises(ValueError, match="Invalid time slot format"):
            TimeSlot.from_bsblan_format("06:00 08:00")

    def test_time_slot_from_invalid_format_bad_time(self) -> None:
        """Test parsing format with bad time values raises ValueError."""
        with pytest.raises(ValueError, match="Invalid time slot format"):
            TimeSlot.from_bsblan_format("25:00-08:00")

    def test_time_slot_roundtrip(self) -> None:
        """Test that converting to and from BSB-LAN format preserves values."""
        original = TimeSlot(start=time(6, 30), end=time(17, 45))
        bsblan_str = original.to_bsblan_format()
        parsed = TimeSlot.from_bsblan_format(bsblan_str)
        assert parsed.start == original.start
        assert parsed.end == original.end


class TestDaySchedule:
    """Test cases for DaySchedule dataclass."""

    def test_empty_day_schedule(self) -> None:
        """Test creating an empty day schedule."""
        schedule = DaySchedule()
        assert schedule.slots == []

    def test_day_schedule_with_slots(self) -> None:
        """Test creating a day schedule with time slots."""
        slots = [
            TimeSlot(time(6, 0), time(8, 0)),
            TimeSlot(time(17, 0), time(21, 0)),
        ]
        schedule = DaySchedule(slots=slots)
        assert len(schedule.slots) == 2

    def test_day_schedule_to_bsblan_format(self) -> None:
        """Test converting day schedule to BSB-LAN format."""
        schedule = DaySchedule(
            slots=[
                TimeSlot(time(6, 0), time(8, 0)),
                TimeSlot(time(17, 0), time(21, 0)),
            ]
        )
        assert schedule.to_bsblan_format() == "06:00-08:00 17:00-21:00"

    def test_day_schedule_to_bsblan_format_empty(self) -> None:
        """Test converting empty day schedule to BSB-LAN format."""
        schedule = DaySchedule()
        assert schedule.to_bsblan_format() == ""

    def test_day_schedule_to_bsblan_format_single_slot(self) -> None:
        """Test converting day schedule with single slot."""
        schedule = DaySchedule(slots=[TimeSlot(time(6, 0), time(8, 0))])
        assert schedule.to_bsblan_format() == "06:00-08:00"

    def test_day_schedule_from_bsblan_format(self) -> None:
        """Test parsing day schedule from BSB-LAN format."""
        schedule = DaySchedule.from_bsblan_format("06:00-08:00 17:00-21:00")
        assert len(schedule.slots) == 2
        assert schedule.slots[0].start == time(6, 0)
        assert schedule.slots[1].start == time(17, 0)

    def test_day_schedule_from_bsblan_format_empty(self) -> None:
        """Test parsing empty string returns empty schedule."""
        schedule = DaySchedule.from_bsblan_format("")
        assert schedule.slots == []

    def test_day_schedule_from_bsblan_format_undefined(self) -> None:
        """Test parsing '---' returns empty schedule."""
        schedule = DaySchedule.from_bsblan_format("---")
        assert schedule.slots == []

    def test_day_schedule_max_slots_valid(self) -> None:
        """Test that 3 slots (BSB-LAN max) is valid."""
        schedule = DaySchedule(
            slots=[
                TimeSlot(time(6, 0), time(8, 0)),
                TimeSlot(time(12, 0), time(13, 0)),
                TimeSlot(time(17, 0), time(21, 0)),
            ]
        )
        assert len(schedule.slots) == 3

    def test_day_schedule_too_many_slots(self) -> None:
        """Test that more than 3 slots raises ValueError."""
        with pytest.raises(ValueError, match="maximum 3 time slots per day"):
            DaySchedule(
                slots=[
                    TimeSlot(time(6, 0), time(7, 0)),
                    TimeSlot(time(8, 0), time(9, 0)),
                    TimeSlot(time(10, 0), time(11, 0)),
                    TimeSlot(time(12, 0), time(13, 0)),
                ]
            )

    def test_day_schedule_roundtrip(self) -> None:
        """Test that converting to and from BSB-LAN format preserves values."""
        original = DaySchedule(
            slots=[
                TimeSlot(time(6, 0), time(8, 0)),
                TimeSlot(time(17, 0), time(21, 0)),
            ]
        )
        bsblan_str = original.to_bsblan_format()
        parsed = DaySchedule.from_bsblan_format(bsblan_str)
        assert len(parsed.slots) == len(original.slots)
        for orig_slot, parsed_slot in zip(original.slots, parsed.slots, strict=True):
            assert orig_slot.start == parsed_slot.start
            assert orig_slot.end == parsed_slot.end


class TestDHWSchedule:
    """Test cases for DHWSchedule dataclass."""

    def test_empty_dhw_schedule(self) -> None:
        """Test creating an empty DHW schedule."""
        schedule = DHWSchedule()
        assert schedule.monday is None
        assert schedule.tuesday is None
        assert not schedule.has_any_schedule()

    def test_dhw_schedule_with_days(self) -> None:
        """Test creating a DHW schedule with multiple days."""
        monday = DaySchedule(slots=[TimeSlot(time(6, 0), time(8, 0))])
        tuesday = DaySchedule(slots=[TimeSlot(time(7, 0), time(9, 0))])
        schedule = DHWSchedule(monday=monday, tuesday=tuesday)
        assert schedule.monday is not None
        assert schedule.tuesday is not None
        assert schedule.wednesday is None

    def test_dhw_schedule_has_any_schedule_true(self) -> None:
        """Test has_any_schedule returns True when a day is set."""
        schedule = DHWSchedule(
            monday=DaySchedule(slots=[TimeSlot(time(6, 0), time(8, 0))])
        )
        assert schedule.has_any_schedule() is True

    def test_dhw_schedule_has_any_schedule_false(self) -> None:
        """Test has_any_schedule returns False when no days are set."""
        schedule = DHWSchedule()
        assert schedule.has_any_schedule() is False

    def test_dhw_schedule_all_days(self) -> None:
        """Test setting all days of the week."""
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
        assert schedule.has_any_schedule() is True
        assert schedule.monday is not None
        assert schedule.sunday is not None

    def test_dhw_schedule_weekend_only(self) -> None:
        """Test setting only weekend days."""
        weekend = DaySchedule(
            slots=[
                TimeSlot(time(8, 0), time(10, 0)),
                TimeSlot(time(18, 0), time(22, 0)),
            ]
        )
        schedule = DHWSchedule(saturday=weekend, sunday=weekend)
        assert schedule.saturday is not None
        assert schedule.sunday is not None
        assert schedule.monday is None
        assert schedule.has_any_schedule() is True
