"""Evidence-backed schedule profile declarations and discovery outcomes.

Profiles assert weekday meaning; runtime probes only check compatibility. A
provenance string records evidence supplied by the profile author, not independent
certification by this library. Never infer the active table from firmware alone.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .schedules import WEEKDAYS, ScheduleMapping, ScheduleMappings

ScheduleKind = Literal["heating", "hot_water"]


class ScheduleProfileIdentity(BaseModel):
    """Exact installation scope certified by a profile's independent evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    firmware_version: str
    bus: Literal["BSB", "LPB"]
    destination: int
    controller: str
    family: int
    variant: int
    table: str

    @field_validator("firmware_version", "controller", "table")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject absent provenance scope rather than accepting wildcard matches."""
        if not value.strip():
            msg = "Profile identity requires nonempty text"
            raise ValueError(msg)
        return value


class ScheduleProfile(BaseModel):
    """Weekday mappings and their provenance for exactly one installation scope."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    id: str
    evidence: str
    identity: ScheduleProfileIdentity
    mappings: ScheduleMappings
    table_parameters: tuple[tuple[str, str], ...] = ()

    @field_validator("id", "evidence")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Require an auditable identifier and an evidence reference."""
        if not value.strip():
            msg = "Profile ID and evidence must be nonempty"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def require_mapping(self) -> ScheduleProfile:
        """Require certification for at least one schedule group."""
        if not self.mappings.heating and self.mappings.hot_water is None:
            msg = "Profile requires at least one schedule mapping"
            raise ValueError(msg)
        if self.table_parameters:
            mappings = tuple(self.mappings.heating.values()) + (
                (self.mappings.hot_water,)
                if self.mappings.hot_water is not None
                else ()
            )
            expected = {
                getattr(mapping, day) for mapping in mappings for day in WEEKDAYS
            }
            declared = dict(self.table_parameters)
            if (
                len(declared) != len(self.table_parameters)
                or set(declared) != expected
                or any(not name.strip() for name in declared.values())
            ):
                msg = "Table signature must name every mapped ID exactly once"
                raise ValueError(msg)
        return self


class ScheduleAvailability(BaseModel):
    """Group enablement and repair/retry advice, not a schedule snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ScheduleKind
    circuit: int | None
    status: Literal["enabled", "unknown", "incompatible", "retry"]
    reason: str
    source: Literal["manual", "profile"] | None = None
    profile_id: str | None = None

    @property
    def enabled(self) -> bool:
        """Return whether the group can be used without a mapping repair."""
        return self.status == "enabled"

    @property
    def repair_required(self) -> bool:
        """Return whether a mapping override or supported profile is needed."""
        return self.status in {"unknown", "incompatible"}

    @property
    def retry_required(self) -> bool:
        """Return whether discovery was inconclusive and should be retried."""
        return self.status == "retry"


class ScheduleCandidateProbe(BaseModel):
    """Diagnostic compatibility only; weekday meaning still needs confirmation."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    candidate_id: str
    evidence: str
    kind: Literal["hot_water"] = "hot_water"
    mapping: ScheduleMapping
    status: Literal["compatible", "incompatible", "retry"]
    incompatible_parameters: tuple[str, ...] = ()
    retry_parameters: tuple[str, ...] = ()
    enabled: Literal[False] = False
    requires_confirmation: Literal[True] = True

    @property
    def retry_required(self) -> bool:
        """Return whether missing/inactive/transient data warrants another probe."""
        return self.status == "retry"


# Owner-confirmed firmware table plus live JC/JQ evidence; no blanket claim for
# other builds or custom tables. See docs/schedule-profiles.md and the sanitized
# tests/fixtures/rvs21_schedule_profile.json provenance/command excerpts.
_RVS21_HEATING_1_INTEGER = ScheduleMapping(
    **{day: str(501 + index) for index, day in enumerate(WEEKDAYS)}
)
_RVS21_HEATING_2_INTEGER = ScheduleMapping(
    **{day: str(521 + index) for index, day in enumerate(WEEKDAYS)}
)
_RVS21_HOT_WATER_INTEGER = ScheduleMapping(
    **{day: str(561 + index) for index, day in enumerate(WEEKDAYS)}
)
_RVS21_HEATING_1_DECIMAL = ScheduleMapping(
    **{
        day: "501" if index == 0 else f"501.{index}"
        for index, day in enumerate(WEEKDAYS)
    }
)
_RVS21_HEATING_2_DECIMAL = ScheduleMapping(
    **{
        day: "521" if index == 0 else f"521.{index}"
        for index, day in enumerate(WEEKDAYS)
    }
)
_RVS21_HOT_WATER_DECIMAL = ScheduleMapping(
    **{
        day: "561" if index == 0 else f"561.{index}"
        for index, day in enumerate(WEEKDAYS)
    }
)
STANDARD_SCHEDULE_PROFILES: tuple[ScheduleProfile, ...] = (
    ScheduleProfile(
        id="rvs21-211-127-integer-20251124",
        evidence="docs/schedule-profiles.md#verified-rvs21-profile",
        identity=ScheduleProfileIdentity(
            firmware_version="5.0.82-20251124154226",
            bus="BSB",
            destination=0,
            controller="RVS21.831F/127",
            family=211,
            variant=127,
            table="rvs21-211-127-integer-weekdays-v1",
        ),
        mappings=ScheduleMappings(
            heating={1: _RVS21_HEATING_1_INTEGER, 2: _RVS21_HEATING_2_INTEGER},
            hot_water=_RVS21_HOT_WATER_INTEGER,
        ),
        table_parameters=tuple(
            (getattr(mapping, day), day.title())
            for mapping in (
                _RVS21_HEATING_1_INTEGER,
                _RVS21_HEATING_2_INTEGER,
                _RVS21_HOT_WATER_INTEGER,
            )
            for day in WEEKDAYS
        ),
    ),
    ScheduleProfile(
        id="rvs21-211-127-decimal-20261120",
        evidence="docs/schedule-profiles.md#verified-rvs21-profile",
        identity=ScheduleProfileIdentity(
            firmware_version="5.0.82-20251124154226",
            bus="BSB",
            destination=0,
            controller="RVS21.831F/127",
            family=211,
            variant=127,
            table="rvs21-211-127-decimal-weekdays-v1",
        ),
        mappings=ScheduleMappings(
            heating={1: _RVS21_HEATING_1_DECIMAL, 2: _RVS21_HEATING_2_DECIMAL},
            hot_water=_RVS21_HOT_WATER_DECIMAL,
        ),
        table_parameters=tuple(
            (getattr(mapping, day), day.title())
            for mapping in (
                _RVS21_HEATING_1_DECIMAL,
                _RVS21_HEATING_2_DECIMAL,
                _RVS21_HOT_WATER_DECIMAL,
            )
            for day in WEEKDAYS
        ),
    ),
)
