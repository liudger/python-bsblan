"""Shared schedule values, observations, and BSB-LAN interval encoding."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

from .exceptions import BSBLANUnsupportedFeatureError
from .models import EntityInfo

Weekday = Literal[
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
]
WEEKDAYS: Final[tuple[Weekday, ...]] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
MAX_TIME_SLOTS_PER_DAY: Final = 3
_DISABLED_SLOT: Final = "##:##-##:##"


@dataclass(frozen=True)
class TimeSlot:
    """One naive, minute-precision interval with an exclusive end."""

    start: time
    end: time

    def __post_init__(self) -> None:
        """Reject values that would be truncated or misrepresented on the bus."""
        for value in (self.start, self.end):
            if (
                not isinstance(value, time)
                or value.tzinfo is not None
                or value.second
                or value.microsecond
            ):
                msg = "Schedule times must be naive, minute-precision time values"
                raise ValueError(msg)
        if self.start >= self.end:
            msg = "Schedule start must be before end"
            raise ValueError(msg)


@dataclass(frozen=True)
class DaySchedule:
    """Up to three non-overlapping intervals; no slots expresses clear intent."""

    slots: tuple[TimeSlot, ...] = ()

    def __post_init__(self) -> None:
        """Validate and defensively copy slots, preserving their order."""
        if not isinstance(self.slots, (tuple, list)):
            msg = "Schedule slots must be a sequence of TimeSlot values"
            raise ValueError(msg)  # noqa: TRY004 - uniform value validation
        if len(self.slots) > MAX_TIME_SLOTS_PER_DAY or any(
            not isinstance(slot, TimeSlot) for slot in self.slots
        ):
            msg = "A day supports at most three TimeSlot values"
            raise ValueError(msg)
        slots = tuple(TimeSlot(slot.start, slot.end) for slot in self.slots)
        if any(
            slot.start < other.end and other.start < slot.end
            for i, slot in enumerate(slots)
            for other in slots[i + 1 :]
        ):
            msg = "Overlapping schedule intervals are unsupported"
            raise ValueError(msg)
        object.__setattr__(self, "slots", slots)

    @classmethod
    def from_bsblan_format(cls, value: str) -> DaySchedule:
        """Parse active and disabled physical slots, never inactive entities."""
        if not isinstance(value, str):
            msg = "Schedule text must be a string"
            raise ValueError(msg)  # noqa: TRY004 - uniform codec rejection
        tokens = value.split()
        if not tokens or len(tokens) > MAX_TIME_SLOTS_PER_DAY:
            msg = "Unsupported physical schedule slot count"
            raise ValueError(msg)
        slots = []
        for token in tokens:
            if token == _DISABLED_SLOT:
                continue
            match = re.fullmatch(r"([0-9]{2}):([0-9]{2})-([0-9]{2}):([0-9]{2})", token)
            if match is None:
                msg = "Unsupported schedule interval format"
                raise ValueError(msg)
            start_h, start_m, end_h, end_m = map(int, match.groups())
            slots.append(TimeSlot(time(start_h, start_m), time(end_h, end_m)))
        return cls(slots=tuple(slots))

    def to_bsblan_format(self) -> str:
        """Serialize active intervals; a verified clear encoding is not known."""
        validated = DaySchedule(self.slots)
        if not validated.slots:
            msg = "Schedule clear encoding has not been verified for this device"
            raise BSBLANUnsupportedFeatureError(msg)
        return " ".join(
            f"{slot.start:%H:%M}-{slot.end:%H:%M}" for slot in validated.slots
        )


@dataclass(frozen=True)
class ScheduleUpdate:
    """A partial update: None leaves a day unchanged, an empty day requests clear."""

    monday: DaySchedule | None = None
    tuesday: DaySchedule | None = None
    wednesday: DaySchedule | None = None
    thursday: DaySchedule | None = None
    friday: DaySchedule | None = None
    saturday: DaySchedule | None = None
    sunday: DaySchedule | None = None

    def __post_init__(self) -> None:
        """Reject raw values and defensively copy every populated day."""
        for name in WEEKDAYS:
            day = getattr(self, name)
            if day is not None:
                if not isinstance(day, DaySchedule):
                    msg = f"{name} must be a DaySchedule or None"
                    raise ValueError(msg)
                object.__setattr__(self, name, DaySchedule(day.slots))


class ScheduleMapping(BaseModel):
    """Caller-confirmed weekday IDs for one device target and schedule group."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    monday: str
    tuesday: str
    wednesday: str
    thursday: str
    friday: str
    saturday: str
    sunday: str

    @field_validator(*WEEKDAYS)
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Keep the exact canonical ID spelling used by /JQ and /JS."""
        if not re.fullmatch(r"[1-9][0-9]*(?:\.[1-9])?", value):
            msg = "Invalid schedule parameter ID"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_unique(self) -> ScheduleMapping:
        """Reject IDs assigned to more than one day."""
        if len({getattr(self, name) for name in WEEKDAYS}) != 7:
            msg = "Schedule parameter IDs must be unique"
            raise ValueError(msg)
        return self


@dataclass(frozen=True, eq=False)
class _CircuitMappings(Mapping[int, ScheduleMapping]):
    """A tuple-backed read-only mapping that supports normal deep copying."""

    _entries: tuple[tuple[int, ScheduleMapping], ...]

    def __getitem__(self, key: int) -> ScheduleMapping:
        """Look up a profile without exposing a mutable backing dictionary."""
        for circuit, profile in self._entries:
            if circuit == key:
                return profile
        raise KeyError(key)

    def __iter__(self) -> Iterator[int]:
        """Iterate configured circuit identifiers in canonical order."""
        return (circuit for circuit, _ in self._entries)

    def __len__(self) -> int:
        """Return the number of configured circuits."""
        return len(self._entries)


class ScheduleMappings(BaseModel):
    """Immutable per-client mappings; absent groups have no implicit profile."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        revalidate_instances="always",
        validate_default=True,
    )

    hot_water: ScheduleMapping | None = None
    heating: Mapping[int, ScheduleMapping] = Field(default_factory=dict)

    @field_validator("heating", mode="before")
    @classmethod
    def validate_circuits(cls, value: Any) -> dict[int, Any]:
        """Normalize canonical JSON IDs without accepting coercion or collisions."""
        if not isinstance(value, Mapping):
            msg = "Heating profiles must be a circuit-keyed mapping"
            raise ValueError(msg)  # noqa: TRY004 - pydantic validation error
        normalized: dict[int, Any] = {}
        for key, profile in value.items():
            if type(key) is int and key in (1, 2):
                circuit = key
            elif type(key) is str and key in ("1", "2"):
                circuit = int(key)
            else:
                msg = "Heating circuit keys must be 1 or 2"
                raise ValueError(msg)
            if circuit in normalized:
                msg = "Duplicate heating circuit after key normalization"
                raise ValueError(msg)
            normalized[circuit] = profile
        return normalized

    @field_validator("heating", mode="after")
    @classmethod
    def freeze_heating(
        cls, value: Mapping[int, ScheduleMapping]
    ) -> Mapping[int, ScheduleMapping]:
        """Capture a read-only copy, including the empty default collection."""
        return _CircuitMappings(tuple(sorted(value.items())))

    @field_serializer("heating")
    def serialize_heating(
        self, value: Mapping[int, ScheduleMapping]
    ) -> dict[int, ScheduleMapping]:
        """Serialize read-only internals as a normal JSON-compatible mapping."""
        return dict(value)


class _ScheduleMetadata(EntityInfo[str]):
    """An immutable copy of the scalar metadata attached to an observation."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class ScheduleDay(BaseModel):
    """One observed day; unavailable and unsupported text are never clear intent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    weekday: Weekday
    parameter_id: str
    status: Literal["readable", "empty", "unavailable", "unparsed"]
    raw_value: str | None = None
    metadata: _ScheduleMetadata | None = None
    schedule: DaySchedule | None = None
    reason: str | None = None
    reason_code: (
        Literal["missing", "inactive", "device_error", "unsupported_format"] | None
    ) = None
    error_code: int | None = None

    @model_validator(mode="after")
    def validate_status(self) -> ScheduleDay:
        """Keep structured values consistent with the observation status."""
        if self.status in {"readable", "empty"}:
            if self.schedule is None or bool(self.schedule.slots) != (
                self.status == "readable"
            ):
                msg = "Parsed schedule must agree with readable/empty status"
                raise ValueError(msg)
        elif self.schedule is not None:
            msg = "Unavailable or unparsed days cannot contain a schedule"
            raise ValueError(msg)
        return self


class ScheduleSnapshot(BaseModel):
    """A fresh immutable observation, not an atomic week or write verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["hot_water", "heating"]
    circuit: int | None
    received_at: datetime
    days: tuple[ScheduleDay, ...]

    @model_validator(mode="after")
    def validate_week(self) -> ScheduleSnapshot:
        """Require seven ordered days, UTC-compatible time and a valid target."""
        if tuple(day.weekday for day in self.days) != WEEKDAYS:
            msg = "A snapshot requires seven canonical ordered weekdays"
            raise ValueError(msg)
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            msg = "A snapshot requires an aware receipt timestamp"
            raise ValueError(msg)
        if (self.kind == "heating" and self.circuit not in (1, 2)) or (
            self.kind == "hot_water" and self.circuit is not None
        ):
            msg = "Snapshot circuit does not match the schedule group"
            raise ValueError(msg)
        return self

    def day(self, weekday: Weekday) -> ScheduleDay:
        """Look up an observed day by its canonical weekday name."""
        return self.days[WEEKDAYS.index(weekday)]

    @computed_field
    @property
    def complete(self) -> bool:
        """Return whether every day has a supported structured value."""
        return all(day.status in {"readable", "empty"} for day in self.days)

    @computed_field
    @property
    def retry_required(self) -> bool:
        """Advise later reads for missing/inactive/possibly transient device data."""
        return any(
            day.status == "unavailable" and day.error_code != 7 for day in self.days
        )
