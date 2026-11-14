"""Schedule values are explicit, immutable, and never guess a clear encoding."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, time
from typing import Any

import pytest
from pydantic import ValidationError

from bsblan.exceptions import BSBLANUnsupportedFeatureError
from bsblan.schedules import (
    DaySchedule,
    ScheduleDay,
    ScheduleMapping,
    ScheduleMappings,
    ScheduleSnapshot,
    ScheduleUpdate,
    TimeSlot,
)


def test_parse_active_and_disabled_slots() -> None:
    """Disabled wire slots do not erase or merge active intervals."""
    day = DaySchedule.from_bsblan_format("06:00-08:00 ##:##-##:## 17:00-21:00")
    assert day.slots == (
        TimeSlot(time(6), time(8)),
        TimeSlot(time(17), time(21)),
    )
    assert day.to_bsblan_format() == "06:00-08:00 17:00-21:00"
    assert DaySchedule.from_bsblan_format("##:##-##:##").slots == ()


def test_three_slots_roundtrip_preserves_order() -> None:
    """The codec retains physical interval boundaries, not sorted guesses."""
    text = "17:00-21:00 06:00-08:00 12:00-13:00"
    day = DaySchedule.from_bsblan_format(text)
    assert day.to_bsblan_format() == text
    assert DaySchedule.from_bsblan_format(day.to_bsblan_format()) == day


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "---",
        "None",
        "   ",
        "6:00-07:00",
        "06:00-24:00",
        "22:00-06:00",
        "06:00-06:00",
        "06:00:00-07:00",
        "06:00-##:##",
        "##:##-##:## " * 4,
        "06:00-08:00 07:00-09:00",
        "not a schedule",
        0,
        [],
    ],
)
def test_unsupported_text_is_not_an_empty_day(value) -> None:
    """Inactive, malformed, or unrepresentable text cannot become clear intent."""
    with pytest.raises(ValueError, match=r".+"):
        DaySchedule.from_bsblan_format(value)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (time(8), time(6)),
        (time(6), time(6)),
        (time(6, tzinfo=UTC), time(7, tzinfo=UTC)),
        (time(6, 0, 1), time(7)),
        (time(6), time(7, microsecond=1)),
        ("06:00", time(7)),
        (time(6), None),
    ],
)
def test_invalid_slot_cannot_be_serialized(start, end) -> None:
    """Minute-only naive intervals prevent silently truncated writes."""
    with pytest.raises(ValueError, match="Schedule"):
        TimeSlot(start, end)


@pytest.mark.parametrize(
    "slots",
    [
        [TimeSlot(time(6), time(7))] * 4,
        [TimeSlot(time(6), time(8)), TimeSlot(time(7), time(9))],
        ["06:00-07:00"],
        None,
        "06:00-07:00",
    ],
)
def test_invalid_slots_cannot_be_written(slots) -> None:
    """Bad types, overlapping intervals, and excess slots fail locally."""
    with pytest.raises(ValueError, match=r"Schedule|day|Overlapping"):
        DaySchedule(slots=slots)


def test_values_copy_input_and_are_frozen() -> None:
    """A caller's list cannot mutate a snapshot or pending update."""
    slots = [TimeSlot(time(6), time(8))]
    day = DaySchedule(slots=slots)
    slots.clear()
    assert day.slots == (TimeSlot(time(6), time(8)),)
    with pytest.raises(FrozenInstanceError):
        day.slots[0].start = time(5)
    with pytest.raises(FrozenInstanceError):
        day.slots = ()
    update = ScheduleUpdate(monday=day)
    with pytest.raises(FrozenInstanceError):
        update.monday = None
    assert update.tuesday is None


def test_empty_day_is_intent_not_an_assumed_wire_encoding() -> None:
    """Clear intent is representable but requires device-verified encoding."""
    update = ScheduleUpdate(tuesday=DaySchedule())
    assert update.monday is None
    assert update.tuesday.slots == ()
    with pytest.raises(BSBLANUnsupportedFeatureError, match="clear"):
        update.tuesday.to_bsblan_format()


def test_update_rejects_non_day_payload() -> None:
    """Raw strings cannot bypass the schedule codec through a command."""
    with pytest.raises(ValueError, match="DaySchedule"):
        ScheduleUpdate(monday="06:00-07:00")


DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
IDS = ("700", "700.1", "700.2", "700.3", "700.4", "700.5", "700.6")


def mapping_values() -> dict[str, str]:
    """Create a synthetic mapping independently of production constants."""
    return dict(zip(DAYS, IDS, strict=True))


@pytest.mark.parametrize("bad", [1, True, "0", "01", "1.0", "1.10", "1,2", "1!2", " 1"])
def test_mapping_rejects_invalid_id(bad) -> None:
    """Only exact canonical string IDs reach the device request builder."""
    values = mapping_values()
    values["monday"] = bad
    with pytest.raises(ValidationError):
        ScheduleMapping(**values)


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "extra"])
def test_mapping_requires_seven_distinct_weekdays(mutation: str) -> None:
    """An incomplete or ambiguous mapping cannot configure a group."""
    values = mapping_values()
    if mutation == "duplicate":
        values["monday"] = values["tuesday"]
    elif mutation == "missing":
        values.pop("sunday")
    else:
        values["holiday"] = "701"
    with pytest.raises(ValidationError):
        ScheduleMapping(**values)


def test_mapping_configuration_is_immutable_and_copied() -> None:
    """Reusing input dictionaries cannot retarget an existing client's group."""
    values = mapping_values()
    profiles = {1: ScheduleMapping(**values)}
    configured = ScheduleMappings(heating=profiles)
    values["monday"] = "900"
    profiles.clear()
    assert configured.heating[1].monday == "700"
    assert configured.hot_water is None
    assert 2 not in configured.heating
    with pytest.raises(ValidationError):
        configured.heating[1].monday = "900"
    with pytest.raises(TypeError, match="assignment"):
        configured.heating[1] = ScheduleMapping(**mapping_values())
    with pytest.raises(ValidationError):
        configured.heating = {}


def test_default_heating_collection_is_immutable() -> None:
    """An unconfigured default cannot be mutated to bypass profile validation."""
    configured = ScheduleMappings()
    assert dict(configured.heating) == {}
    with pytest.raises(TypeError, match="assignment"):
        configured.heating[1] = ScheduleMapping(**mapping_values())


@pytest.mark.parametrize("key", [1, 2, "1", "2"])
def test_heating_circuit_keys_normalize_canonical_identifiers(key) -> None:
    """Python and JSON configuration identify the same supported circuit."""
    configured = ScheduleMappings(heating={key: mapping_values()})
    assert tuple(configured.heating) == (int(key),)
    assert configured.heating[int(key)].monday == "700"


@pytest.mark.parametrize("key", [True, False, 1.0, 2.0, 0, 3, "01", "1.0", " 1", "x"])
def test_heating_rejects_ambiguous_or_unsupported_circuit_keys(key) -> None:
    """Coercion must not turn bool/float/noncanonical IDs into a circuit."""
    with pytest.raises(ValidationError):
        ScheduleMappings(heating={key: mapping_values()})


@pytest.mark.parametrize("value", [None, [], "1", [(1, mapping_values())]])
def test_heating_requires_a_mapping_collection(value) -> None:
    """An invalid collection cannot be interpreted as configured circuits."""
    with pytest.raises(ValidationError):
        ScheduleMappings(heating=value)


@pytest.mark.parametrize("value", [None, {}, "profile"])
def test_heating_rejects_invalid_profile_values(value) -> None:
    """Present circuit entries require a complete validated weekday mapping."""
    with pytest.raises(ValidationError):
        ScheduleMappings(heating={1: value})


def test_heating_rejects_collisions_after_key_normalization() -> None:
    """Python 1 and JSON '1' must not silently overwrite a configured profile."""
    with pytest.raises(ValidationError):
        ScheduleMappings(heating={1: mapping_values(), "1": mapping_values()})


def test_numbered_heating_fields_are_not_an_alternate_configuration() -> None:
    """Only the keyed collection can configure circuit profiles."""
    with pytest.raises(ValidationError):
        ScheduleMappings.model_validate({"heating_1": mapping_values()})


def test_heating_collection_serializes_and_roundtrips_without_aliases() -> None:
    """Immutable internals remain JSON-configurable without losing exact IDs."""
    configured = ScheduleMappings(heating={2: mapping_values(), 1: mapping_values()})
    assert tuple(configured.heating) == (1, 2)
    serialized = configured.model_dump()
    serialized["heating"][1]["monday"] = "900"
    assert configured.heating[1].monday == "700"
    encoded = configured.model_dump(mode="json")
    assert set(encoded["heating"]) == {"1", "2"}
    assert encoded["heating"]["1"]["tuesday"] == "700.1"
    restored = ScheduleMappings.model_validate_json(configured.model_dump_json())
    assert tuple(restored.heating) == (1, 2)
    assert restored.heating[2].tuesday == "700.1"
    with pytest.raises(TypeError, match="assignment"):
        restored.heating[2] = ScheduleMapping(**mapping_values())


def test_heating_collection_supports_normal_configuration_copying() -> None:
    """A read-only field must not break pydantic or standard deep-copy utilities."""
    configured = ScheduleMappings(heating={1: mapping_values()})
    copies = (deepcopy(configured), configured.model_copy(deep=True))
    for copied in copies:
        assert copied is not configured
        assert copied.heating[1].tuesday == "700.1"
        assert dict(copied.heating) == dict(configured.heating)
        with pytest.raises(TypeError, match="assignment"):
            copied.heating[1] = ScheduleMapping(**mapping_values())


def snapshot(**first_day: Any) -> ScheduleSnapshot:
    """Build seven observations, with caller-controlled first-day status."""
    days = [
        ScheduleDay(
            weekday=name, parameter_id=param, status="empty", schedule=DaySchedule()
        )
        for name, param in zip(DAYS, IDS, strict=True)
    ]
    if first_day:
        days[0] = ScheduleDay(weekday="monday", parameter_id="700", **first_day)
    return ScheduleSnapshot(
        kind="heating", circuit=1, received_at=datetime.now(UTC), days=days
    )


@pytest.mark.parametrize(
    ("status", "reason", "error", "complete", "retry"),
    [
        ("empty", None, None, True, False),
        ("unavailable", "missing", None, False, True),
        ("unavailable", "inactive", None, False, True),
        ("unavailable", "device_error", 261, False, True),
        ("unavailable", "device_error", 42, False, True),
        ("unavailable", "device_error", 7, False, False),
        ("unparsed", "unsupported_format", None, False, False),
    ],
)
def test_observation_outcomes_drive_retry(
    status, reason, error, complete, retry
) -> None:
    """A returned object is not automatically a successfully refreshed week."""
    result = snapshot(
        status=status,
        reason_code=reason,
        error_code=error,
        schedule=DaySchedule() if status == "empty" else None,
    )
    assert result.complete is complete
    assert result.retry_required is retry
    serialized = result.model_dump(mode="json")
    assert serialized["complete"] is complete
    assert serialized["retry_required"] is retry
    assert serialized["days"][0]["parameter_id"] == "700"
    assert serialized["received_at"].endswith("Z")


def test_snapshot_has_no_mutable_nested_observations() -> None:
    """Days, slots, metadata and source buffers cannot mutate an observation."""
    raw = {"name": "x", "value": "06:00-08:00", "unit": "", "desc": "", "dataType": 9}
    result = snapshot(
        status="readable",
        raw_value="06:00-08:00",
        metadata=raw,
        schedule=DaySchedule.from_bsblan_format("06:00-08:00"),
    )
    raw["name"] = "changed"
    assert result.day("monday").metadata.name == "x"
    with pytest.raises(ValidationError):
        result.day("monday").metadata.name = "changed"
    with pytest.raises(ValidationError):
        result.day("monday").status = "unavailable"
    with pytest.raises(FrozenInstanceError):
        result.day("monday").schedule.slots[0].start = time(5)
    with pytest.raises(ValidationError):
        result.days = ()
    assert isinstance(result.days, tuple)
    assert result.complete
    assert not result.retry_required
    assert result.model_dump(mode="json")["days"][0]["schedule"]["slots"] == [
        {"start": "06:00:00", "end": "08:00:00"}
    ]
    with pytest.raises(ValueError, match="not in tuple"):
        result.day("holiday")


@pytest.mark.parametrize(
    "mutation", ["missing", "reordered", "duplicate", "naive", "circuit"]
)
def test_snapshot_rejects_inconsistent_week(mutation: str) -> None:
    """Completeness cannot describe a malformed week or target."""
    original = snapshot()
    values = {
        "kind": original.kind,
        "circuit": original.circuit,
        "received_at": original.received_at,
        "days": original.days,
    }
    if mutation == "missing":
        values["days"] = original.days[:-1]
    elif mutation == "reordered":
        values["days"] = tuple(reversed(original.days))
    elif mutation == "duplicate":
        values["days"] = (original.days[0],) * 7
    elif mutation == "naive":
        values["received_at"] = datetime(2026, 1, 1)  # noqa: DTZ001
    else:
        values["circuit"] = None
    with pytest.raises(ValidationError):
        ScheduleSnapshot(**values)


@pytest.mark.parametrize(
    ("status", "schedule"),
    [
        ("readable", None),
        ("readable", DaySchedule()),
        ("empty", None),
        ("unavailable", DaySchedule()),
        ("unparsed", DaySchedule()),
    ],
)
def test_day_status_cannot_disguise_a_clear(status, schedule) -> None:
    """Only genuinely parsed days carry writable interval values."""
    with pytest.raises(ValidationError):
        ScheduleDay(
            weekday="monday", parameter_id="700", status=status, schedule=schedule
        )
