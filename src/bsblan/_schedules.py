"""Configured heating and hot-water schedule reads and sequential writes."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from ._permissions import read_write_permission
from ._schedule_profiles import ScheduleProfileResolver, _ScheduleResolution
from .constants import ErrorMsg
from .exceptions import (
    BSBLANError,
    BSBLANInvalidParameterError,
    BSBLANMalformedResponseError,
    BSBLANScheduleMappingError,
    BSBLANScheduleProbeError,
    BSBLANScheduleWriteError,
    BSBLANUnsupportedFeatureError,
)
from .models import DataType
from .schedule_profiles import (
    ScheduleAvailability,
    ScheduleCandidateProbe,
    ScheduleKind,
)
from .schedules import (
    WEEKDAYS,
    DaySchedule,
    ScheduleDay,
    ScheduleMapping,
    ScheduleMappings,
    ScheduleSnapshot,
    ScheduleUpdate,
    Weekday,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def _parse_observation(name: Weekday, param: str, raw: Any) -> ScheduleDay:
    """Keep malformed metadata distinct from unsupported interval text."""
    if (
        not isinstance(raw, dict)
        or "value" not in raw
        or type(raw.get("error")) is not int
    ):
        msg = "Schedule entity requires a value and integer error"
        raise ValueError(msg)
    value = raw["value"]
    if value is not None and not isinstance(value, str):
        msg = "Schedule value must be text or null"
        raise ValueError(msg)
    metadata = raw.copy()
    if raw["error"] and raw.get("dataType") != DataType.TIMEPROG:
        metadata["value"] = None
    common: dict[str, Any] = {
        "weekday": name,
        "parameter_id": param,
        "raw_value": value,
        "metadata": metadata,
    }
    if raw["error"]:
        return ScheduleDay(
            **common,
            status="unavailable",
            reason_code="device_error",
            error_code=raw["error"],
        )
    if value is None or value in {"", "---", "None"}:
        return ScheduleDay(**common, status="unavailable", reason_code="inactive")
    if type(raw.get("dataType")) is not int or raw["dataType"] != DataType.TIMEPROG:
        msg = "Unsupported or missing schedule data type"
        raise ValueError(msg)
    try:
        schedule = DaySchedule.from_bsblan_format(value)
    except ValueError as err:
        return ScheduleDay(
            **common,
            status="unparsed",
            reason_code="unsupported_format",
            reason=str(err),
        )
    return ScheduleDay(
        **common,
        status="readable" if schedule.slots else "empty",
        schedule=schedule,
    )


def _observed_day(
    name: Weekday, param: str, raw: Any, kind: str, circuit: int | None
) -> ScheduleDay:
    """Add target and weekday context to malformed entity failures."""
    try:
        return _parse_observation(name, param, raw)
    except (ValueError, TypeError, AttributeError) as err:
        msg = f"Invalid {kind} schedule circuit {circuit} {name} parameter {param}"
        raise BSBLANMalformedResponseError(msg) from err


def _write_outcome(response: Any, param: str) -> Literal["rejected", "unknown"] | None:
    """Only an exact integer status 1 for the requested ID is acknowledgement."""
    if isinstance(response, dict) and isinstance(response.get(param), dict):
        status = response[param].get("status")
        if type(status) is int:
            return None if status == 1 else "rejected"
    return "unknown"


class ScheduleManager:
    """Reuse validated profiles for reads and freshly probe automatic writes."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        request: Callable[..., Awaitable[dict[str, Any]]],
        set_payload: Callable[[str, str], dict[str, Any]],
        uses_pps_bus: Callable[[], bool],
        mappings: ScheduleMappings,
        bus_writable: Callable[[], bool],
        target_key: Callable[[], tuple[str, int, str | None]],
        profile_resolver: ScheduleProfileResolver,
        metadata_key: Callable[[], object],
        uses_bsb_lpb_bus: Callable[[], bool],
    ) -> None:
        """Capture validated mappings while resolving current transport/metadata."""
        self._request = request
        self._set_payload = set_payload
        self._uses_pps_bus = uses_pps_bus
        self._mappings = ScheduleMappings.model_validate(mappings)
        self._bus_writable = bus_writable
        self._uses_bsb_lpb_bus = uses_bsb_lpb_bus
        self._target_key = target_key
        self._confirmed_target = target_key()
        self._profile_resolver = profile_resolver
        self._metadata_key = metadata_key
        self._profile_lock = asyncio.Lock()
        self._validated_profiles: dict[
            tuple[ScheduleKind, int | None], _ScheduleResolution
        ] = {}
        self._profile_metadata: object = None
        self._profile_generation = 0

    def invalidate_profiles(self) -> None:
        """Discard automatic mapping trust without starting network requests."""
        self._validated_profiles.clear()
        self._profile_generation += 1

    def _check_profile_generation(
        self, generation: int, kind: str, circuit: int | None
    ) -> None:
        """Do not publish or use proof invalidated during an awaited request."""
        if generation != self._profile_generation:
            raise BSBLANScheduleProbeError(kind, circuit, "discovery_invalidated")

    def _profile_key(self) -> object:
        """Bind cached trust to transport, adapter and observed controller scope."""
        return self.profile_guard(), self._profile_resolver.identity_key

    def _check_profile_cache(self) -> None:
        """Invalidate all positive entries after an observed metadata change."""
        if self._validated_profiles and self._profile_key() != self._profile_metadata:
            self.invalidate_profiles()

    def _remember_profiles(self, resolutions: tuple[_ScheduleResolution, ...]) -> None:
        """Cache successful immutable mappings, never probe values or failures."""
        self._profile_metadata = self._profile_key()
        for resolution in resolutions:
            availability = resolution.availability
            if availability.enabled:
                self._validated_profiles[(availability.kind, availability.circuit)] = (
                    _ScheduleResolution(availability, resolution.mapping)
                )

    def profile_guard(self) -> object:
        """Check transport identity and expose cached metadata to the resolver."""
        if self._target_key() != self._confirmed_target:
            raise BSBLANScheduleMappingError(
                kind="discovery", circuit=None, reason="target_changed"
            )
        return self._metadata_key()

    def _mapping(
        self, kind: Literal["hot_water", "heating"], circuit: int | None
    ) -> ScheduleMapping | None:
        """Resolve a manual override while enforcing existing local safety gates."""
        if kind == "heating":
            if type(circuit) is not int or circuit not in (1, 2):
                msg = f"circuit {circuit}"
                raise BSBLANInvalidParameterError(msg)
            mapping = self._mappings.heating.get(circuit)
        else:
            mapping = self._mappings.hot_water
        if self._uses_pps_bus():
            msg = f"{kind} circuit {circuit}: PPS schedules unsupported"
            raise BSBLANUnsupportedFeatureError(msg)
        if self._target_key() != self._confirmed_target:
            raise BSBLANScheduleMappingError(kind, circuit, "target_changed")
        return mapping

    async def discover(
        self, *, refresh: bool = False
    ) -> tuple[ScheduleAvailability, ...]:
        """Reuse validated groups or explicitly refresh read-only discovery."""
        async with self._profile_lock:
            self.profile_guard()
            self._check_profile_cache()
            if refresh:
                self.invalidate_profiles()
            groups: tuple[tuple[ScheduleKind, int | None], ...] = (
                ("heating", 1),
                ("heating", 2),
                ("hot_water", None),
            )
            manual: dict[tuple[ScheduleKind, int | None], ScheduleMapping | None] = (
                {}
                if self._uses_pps_bus()
                else {group: self._mapping(*group) for group in groups}
            )
            automatic = self._validated_profiles.copy()
            missing = tuple(
                group
                for group in manual
                if manual[group] is None and group not in automatic
            )
            generation = self._profile_generation
            fresh = await self._profile_resolver.resolve_many(missing)
            self.profile_guard()
            self._check_profile_cache()
            self._check_profile_generation(generation, "discovery", None)
            if self._uses_pps_bus():
                return tuple(
                    ScheduleAvailability(
                        kind=kind,
                        circuit=circuit,
                        status="unknown",
                        reason="pps_unsupported",
                    )
                    for kind, circuit in groups
                )
            self._remember_profiles(fresh)
            automatic.update(zip(missing, fresh, strict=True))
            return tuple(
                ScheduleAvailability(
                    kind=kind,
                    circuit=circuit,
                    status="enabled",
                    reason="manual_mapping",
                    source="manual",
                )
                if manual[(kind, circuit)] is not None
                else automatic[(kind, circuit)].availability
                for kind, circuit in groups
            )

    async def probe_candidate(self, candidate_id: str) -> ScheduleCandidateProbe:
        """Serialize an explicit diagnostic without promoting its mapping to cache."""
        async with self._profile_lock:
            self._mapping("hot_water", None)
            generation = self._profile_generation
            result = await self._profile_resolver.probe_candidate(candidate_id)
            self.profile_guard()
            self._check_profile_generation(generation, "hot_water", None)
            return result

    @staticmethod
    def _require_available(availability: ScheduleAvailability) -> None:
        """Keep inconclusive probes distinct from mapping-repair failures."""
        kind, circuit = availability.kind, availability.circuit
        if availability.retry_required:
            raise BSBLANScheduleProbeError(kind, circuit, availability.reason)
        if not availability.enabled:
            # Preserve the existing no-profile failure reason for manual clients.
            reason = (
                "mapping_unknown"
                if availability.reason == "profile_unknown"
                else availability.reason
            )
            raise BSBLANScheduleMappingError(kind, circuit, reason)

    async def _resolve(
        self, kind: ScheduleKind, circuit: int | None, *, refresh: bool = False
    ) -> _ScheduleResolution:
        """Prefer overrides, then cached trust, then a serialized fresh probe."""
        async with self._profile_lock:
            mapping = self._mapping(kind, circuit)
            if mapping is not None:
                return _ScheduleResolution(
                    ScheduleAvailability(
                        kind=kind,
                        circuit=circuit,
                        status="enabled",
                        reason="manual_mapping",
                        source="manual",
                    ),
                    mapping,
                )
            self._check_profile_cache()
            if refresh:
                self._validated_profiles.pop((kind, circuit), None)
            elif (cached := self._validated_profiles.get((kind, circuit))) is not None:
                return cached
            generation = self._profile_generation
            resolution = await self._profile_resolver.resolve(kind, circuit)
            self._mapping(kind, circuit)
            self._check_profile_cache()
            self._check_profile_generation(generation, kind, circuit)
            self._require_available(resolution.availability)
            self._remember_profiles((resolution,))
            return resolution

    async def read(
        self, kind: Literal["hot_water", "heating"], circuit: int | None = None
    ) -> ScheduleSnapshot:
        """Fetch fresh day values using an override or validated profile mapping."""
        resolution = await self._resolve(kind, circuit)
        mapping = cast("ScheduleMapping", resolution.mapping)
        days = {name: getattr(mapping, name) for name in WEEKDAYS}
        context = (
            f"Invalid {kind} schedule circuit {circuit} "
            f"response for IDs {list(days.values())}"
        )
        automatic = resolution.availability.source == "profile"
        metadata = self._profile_key()
        generation = self._profile_generation
        try:
            response = resolution.response
            if response is None:
                response = await self._request(
                    params={"Parameter": ",".join(days.values())}
                )
            if not isinstance(response, dict):
                msg = "Expected a schedule response object"
                raise BSBLANMalformedResponseError(msg)
            if automatic:
                if self._profile_key() != metadata:
                    raise BSBLANScheduleMappingError(kind, circuit, "metadata_changed")
                self._check_profile_generation(generation, kind, circuit)
                status = self._profile_resolver.compatibility(mapping, response)
                self._require_available(
                    resolution.availability.model_copy(
                        update={
                            "status": status,
                            "reason": "probe_incomplete"
                            if status == "retry"
                            else "probe_incompatible",
                        }
                    )
                )
            return ScheduleSnapshot(
                kind=kind,
                circuit=circuit,
                received_at=datetime.now(UTC),
                days=tuple(
                    _observed_day(name, param, response[param], kind, circuit)
                    if param in response
                    else ScheduleDay(
                        weekday=name,
                        parameter_id=param,
                        status="unavailable",
                        reason_code="missing",
                    )
                    for name, param in days.items()
                ),
            )
        except BSBLANError as err:
            if automatic:
                self.invalidate_profiles()
            if isinstance(err, BSBLANMalformedResponseError):
                err.message = f"{context}: {err}"
                err.args = (err.message,)
            raise

    def _permission_key(self) -> tuple[object, bool]:
        """Bind individual permission evidence to the current metadata/defaults."""
        return self._profile_key(), self._bus_writable()

    def _ensure_writable(
        self, param: str, key: tuple[object, bool], *, permission: bool | None
    ) -> None:
        """Honor individual flags without treating disabled defaults as a veto."""
        current = self._permission_key()
        if permission is False:
            msg = f"Schedule parameter {param} is not readable and writable"
            raise BSBLANUnsupportedFeatureError(msg)
        if (not key[1] or not current[1]) and current != key:
            msg = f"Schedule parameter {param} needs a fresh permission check"
            raise BSBLANUnsupportedFeatureError(msg)
        if not current[1] and (not self._uses_bsb_lpb_bus() or permission is not True):
            msg = (
                f"Schedule parameter {param} needs explicit read/write permission "
                "(readwrite=0) while gateway defaults disable writes"
            )
            raise BSBLANUnsupportedFeatureError(msg)

    async def _write_permissions(
        self, params: tuple[str, ...], response: dict[str, Any] | None
    ) -> tuple[dict[str, bool | None], tuple[object, bool]]:
        """Check every populated ID before writing, using /JC only when needed."""
        key = self._permission_key()
        permissions = {
            param: read_write_permission(raw) if isinstance(raw, dict) else None
            for param in params
            for raw in [(response or {}).get(param)]
        }
        if not key[1]:
            if not self._uses_bsb_lpb_bus():
                self._ensure_writable(params[0], key, permission=None)
            missing = tuple(param for param in params if permissions[param] is None)
            if missing:
                structure = await self._request(base_path=f"/JC={','.join(missing)}")
                if not isinstance(structure, dict):
                    msg = "Invalid schedule permission structure response"
                    raise BSBLANMalformedResponseError(msg)
                if self._permission_key() != key:
                    msg = "Schedule permission metadata changed during preflight"
                    raise BSBLANUnsupportedFeatureError(msg)
                for param in missing:
                    raw = structure.get(param)
                    if not isinstance(raw, dict):
                        continue
                    valid_type = (
                        type(raw.get("dataType")) is int
                        and raw["dataType"] == DataType.TIMEPROG
                    )
                    valid_error = "error" not in raw or (
                        type(raw["error"]) is int and raw["error"] == 0
                    )
                    permissions[param] = (
                        read_write_permission(raw)
                        if valid_type and valid_error
                        else False
                    )
        for param in params:
            self._ensure_writable(param, key, permission=permissions[param])
        return permissions, key

    async def write(
        self,
        kind: Literal["hot_water", "heating"],
        update: ScheduleUpdate,
        circuit: int | None = None,
    ) -> None:
        """Prevalidate every day, then stop at the first uncertain/rejected write."""
        resolution = await self._resolve(kind, circuit, refresh=True)
        mapping = resolution.mapping
        metadata = self._profile_key()
        generation = self._profile_generation
        if not isinstance(update, ScheduleUpdate):
            msg = "A ScheduleUpdate is required"
            raise BSBLANInvalidParameterError(msg)
        try:
            validated = ScheduleUpdate(
                **{name: getattr(update, name) for name in WEEKDAYS}
            )
        except (ValueError, TypeError) as err:
            raise BSBLANInvalidParameterError(str(err)) from err
        commands = [
            (name, getattr(mapping, name), day.to_bsblan_format())
            for name in WEEKDAYS
            if (day := getattr(validated, name)) is not None
        ]
        if not commands:
            raise BSBLANInvalidParameterError(ErrorMsg.NO_SCHEDULE)
        permissions, permission_key = await self._write_permissions(
            tuple(param for _, param, _ in commands), resolution.response
        )
        acknowledged: list[Weekday] = []
        for index, (name, param, value) in enumerate(commands):
            pending = tuple(command[0] for command in commands[index + 1 :])
            try:
                self._mapping(kind, circuit)
                if resolution.availability.source == "profile":
                    self._check_profile_generation(generation, kind, circuit)
                    if self._profile_key() != metadata:
                        raise BSBLANScheduleMappingError(
                            kind, circuit, "metadata_changed"
                        )
                self._ensure_writable(
                    param, permission_key, permission=permissions[param]
                )
                response = await self._request(
                    base_path="/JS", data=self._set_payload(param, value)
                )
            except BSBLANError as err:
                raise BSBLANScheduleWriteError(
                    kind=kind,
                    circuit=circuit,
                    acknowledged_days=tuple(acknowledged),
                    failed_day=name,
                    parameter_id=param,
                    unattempted_days=pending,
                    outcome="unknown",
                ) from err
            outcome = _write_outcome(response, param)
            if outcome is not None:
                raise BSBLANScheduleWriteError(
                    kind=kind,
                    circuit=circuit,
                    acknowledged_days=tuple(acknowledged),
                    failed_day=name,
                    parameter_id=param,
                    unattempted_days=pending,
                    outcome=outcome,
                )
            acknowledged.append(name)
