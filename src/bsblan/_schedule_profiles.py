"""Read-only schedule identity matching and candidate compatibility probes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from ._schedule_tables import TableKey, TableStatus, table_status
from .exceptions import (
    BSBLANInvalidParameterError,
    BSBLANMalformedResponseError,
    BSBLANScheduleMappingError,
    BSBLANUnsupportedFeatureError,
)
from .models import DataType
from .schedule_profiles import (
    ScheduleAvailability,
    ScheduleCandidateProbe,
    ScheduleKind,
)
from .schedules import WEEKDAYS, ScheduleMapping

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .models import Device
    from .schedule_profiles import ScheduleProfile


@dataclass(frozen=True)
class _ScheduleResolution:
    """Keep the verified mapping and exact probe response together internally."""

    availability: ScheduleAvailability
    mapping: ScheduleMapping | None = None
    response: dict[str, Any] | None = None


def _entity(raw: Any) -> dict[str, Any]:
    """Require raw entity fields before drawing compatibility conclusions."""
    if (
        not isinstance(raw, dict)
        or "value" not in raw
        or type(raw.get("error")) is not int
        or (raw["value"] is not None and not isinstance(raw["value"], str))
    ):
        msg = "Invalid schedule profile probe entity"
        raise BSBLANMalformedResponseError(msg)
    return raw


def _envelope(raw: Any) -> dict[str, Any]:
    """Reject non-object JSON instead of treating it as absent parameters."""
    if not isinstance(raw, dict):
        msg = "Invalid schedule profile probe response"
        raise BSBLANMalformedResponseError(msg)
    return raw


def _parameter_compatibility(
    response: dict[str, Any], param: str
) -> Literal["enabled", "retry", "incompatible"]:
    """Classify one candidate ID without inferring any weekday meaning."""
    if param not in response:
        return "retry"
    raw = _entity(response[param])
    if raw["error"] == 7:
        return "incompatible"
    if raw["error"] or raw["value"] in {None, "", "---", "None"}:
        return "retry"
    if type(raw.get("dataType")) is not int or raw["dataType"] != DataType.TIMEPROG:
        return "incompatible"
    return "enabled"


def _identity_field_status(
    response: dict[str, Any], param: str, expected: DataType
) -> Literal["valid", "retry", "unsupported"]:
    """Classify one controller field without short-circuiting peer validation."""
    if param not in response:
        return "retry"
    raw = _entity(response[param])
    if raw["error"] == 7:
        return "unsupported"
    if raw["error"] or raw["value"] in {None, "", "---", "None"}:
        return "retry"
    if type(raw.get("dataType")) is not int or raw["dataType"] != expected:
        return "unsupported"
    return "valid"


def _controller_values(response: dict[str, Any]) -> tuple[list[str] | None, str]:
    """Validate all controller fields and keep incomplete-data priority."""
    values: list[str] = []
    outcomes = set()
    for param, expected in (
        ("6224", DataType.STRING),
        ("6225", DataType.PLAIN_NUMBER),
        ("6226", DataType.PLAIN_NUMBER),
    ):
        status = _identity_field_status(response, param, expected)
        outcomes.add(status)
        if status == "valid":
            values.append(response[param]["value"])
    if "retry" in outcomes:
        return None, "identity_incomplete"
    if "unsupported" in outcomes or not all(
        re.fullmatch(r"\d+", value, flags=re.ASCII) for value in values[1:]
    ):
        return None, "identity_unsupported"
    return values, "identity_matched"


def _selection_failure(
    verified_count: int, *, incomplete: bool
) -> tuple[Literal["retry", "unknown", "incompatible"], str] | None:
    """Require conclusive and unique table evidence before selecting a profile."""
    if incomplete:
        return "retry", "table_incomplete"
    if verified_count > 1:
        return "unknown", "profile_ambiguous"
    if verified_count == 0:
        return "incompatible", "table_incompatible"
    return None


class ScheduleProfileResolver:
    """Refresh identity and probe candidates without caching failures or writing."""

    def __init__(
        self,
        *,
        request: Callable[..., Awaitable[dict[str, Any]]],
        device: Callable[[], Awaitable[Device]],
        profiles: tuple[ScheduleProfile, ...],
        table: str | None,
        guard: Callable[[], object] = lambda: None,
    ) -> None:
        """Capture immutable profile declarations and the deployment table ID."""
        self._request = request
        self._device = device
        self._profiles = profiles
        self._table = table
        self._guard = guard
        self._identity_key: object = None
        self._table_facts: dict[TableKey, str] = {}
        self._table_revision = 0

    @property
    def identity_key(self) -> object:
        """Return the latest fully observed installation identity for cache guards."""
        return self._identity_key, self._table_revision

    async def _checked_request(
        self, params: dict[str, str] | None = None, *, base_path: str | None = None
    ) -> dict[str, Any]:
        """Reject metadata or transport changes while a probe is in flight."""
        before = self._guard()
        response = (
            await self._request(params=params)
            if params is not None
            else await self._request(base_path=base_path)
        )
        if self._guard() != before:
            raise BSBLANScheduleMappingError(
                kind="discovery", circuit=None, reason="metadata_changed"
            )
        return _envelope(response)

    async def _identity(self) -> tuple[dict[str, Any] | None, str]:
        """Read identity facts, never derive active-table meaning from values."""
        if not self._profiles:
            return None, "profile_unknown"
        if not self._table and not any(p.table_parameters for p in self._profiles):
            return None, "table_unknown"
        self._guard()
        device = await self._device()
        self._guard()
        if device.bus not in {"BSB", "LPB"} or device.busdest is None:
            return None, "bus_unknown_or_unsupported"
        response = await self._checked_request({"Parameter": "6224,6225,6226"})
        values, reason = _controller_values(response)
        if values is None:
            return None, reason
        identity = {
            "firmware_version": device.version,
            "bus": device.bus,
            "destination": device.busdest,
            "controller": values[0],
            "family": int(values[1]),
            "variant": int(values[2]),
            "table": self._table,
        }
        return identity, "identity_matched"

    async def resolve(
        self, kind: ScheduleKind, circuit: int | None
    ) -> _ScheduleResolution:
        """Resolve one group using fresh identity and seven read-only values."""
        return (await self.resolve_many(((kind, circuit),)))[0]

    async def resolve_many(
        self, groups: tuple[tuple[ScheduleKind, int | None], ...]
    ) -> tuple[_ScheduleResolution, ...]:
        """Share one fresh identity read across independent group probes."""
        if not groups:
            return ()
        identity, reason = await self._identity()
        self._identity_key = tuple(identity.items()) if identity is not None else None
        tables: dict[TableKey, TableStatus] = {}
        resolutions = []
        for kind, circuit in groups:
            resolutions.append(
                await self._resolve(kind, circuit, identity, reason, tables)
            )
        return tuple(resolutions)

    @staticmethod
    def _matches_identity(profile: ScheduleProfile, identity: dict[str, Any]) -> bool:
        """Allow automatic table recognition only with a declared complete layout."""
        expected = profile.identity.model_dump()
        if identity["table"] is None and profile.table_parameters:
            expected["table"] = None
        return expected == identity

    async def _verify_table(
        self,
        profile: ScheduleProfile,
        mapping: ScheduleMapping,
        tables: dict[TableKey, TableStatus],
    ) -> TableStatus:
        """Check only this group's declared layout; reuse probes within one call."""
        if not profile.table_parameters:
            return "match"
        names = dict(profile.table_parameters)
        expected = tuple(
            (getattr(mapping, day), names[getattr(mapping, day)]) for day in WEEKDAYS
        )
        key = (expected, profile.identity.destination)
        if key not in tables:
            response = await self._checked_request(
                base_path="/JC=" + ",".join(param for param, _ in expected)
            )
            # Keep immutable observations for invalidation, not a probe cache.
            observed = {
                param: {
                    field: raw.get(field)
                    for field in ("name", "dataType", "destination", "error")
                }
                if isinstance(raw, dict)
                else raw
                for param, _ in expected
                for raw in [response.get(param)]
            }
            fact = json.dumps(observed, sort_keys=True)
            if key in self._table_facts and self._table_facts[key] != fact:
                self._table_revision += 1
            self._table_facts[key] = fact
            tables[key] = table_status(response, expected, profile.identity.destination)
        return tables[key]

    def _matching_candidates(
        self, kind: ScheduleKind, circuit: int | None, identity: dict[str, Any]
    ) -> tuple[list[tuple[ScheduleProfile, ScheduleMapping]], str]:
        """Find source-declared groups without querying or inferring weekday IDs."""
        matches = [
            profile
            for profile in self._profiles
            if self._matches_identity(profile, identity)
        ]
        candidates = []
        for profile in matches:
            mapping = (
                profile.mappings.hot_water
                if kind == "hot_water"
                else profile.mappings.heating.get(circuit)
            )
            if mapping is not None:
                candidates.append((profile, mapping))
        return candidates, "mapping_unknown" if matches else "profile_unknown"

    async def _resolve(
        self,
        kind: ScheduleKind,
        circuit: int | None,
        identity: dict[str, Any] | None,
        reason: str,
        tables: dict[TableKey, TableStatus],
    ) -> _ScheduleResolution:
        """Require a unique matching group before requesting its candidate IDs."""
        common: dict[str, Any] = {"kind": kind, "circuit": circuit}
        if identity is None:
            return _ScheduleResolution(
                ScheduleAvailability(
                    **common,
                    status="retry" if reason == "identity_incomplete" else "unknown",
                    reason=reason,
                )
            )
        candidates, missing_reason = self._matching_candidates(kind, circuit, identity)
        if not candidates:
            return _ScheduleResolution(
                ScheduleAvailability(
                    **common,
                    status="unknown",
                    reason=missing_reason,
                )
            )
        verified = []
        incomplete = False
        for profile, mapping in candidates:
            result = await self._verify_table(profile, mapping, tables)
            if result == "match":
                verified.append((profile, mapping))
            incomplete |= result == "retry"
        failure = _selection_failure(len(verified), incomplete=incomplete)
        if failure is not None:
            status, reason = failure
            return _ScheduleResolution(
                ScheduleAvailability(**common, status=status, reason=reason)
            )
        profile, mapping = verified[0]
        response = await self._checked_request(
            {"Parameter": ",".join(getattr(mapping, name) for name in WEEKDAYS)}
        )
        status = self.compatibility(mapping, response)
        availability = ScheduleAvailability(
            **common,
            status=status,
            reason={
                "enabled": "probe_compatible",
                "retry": "probe_incomplete",
                "incompatible": "probe_incompatible",
            }[status],
            source="profile",
            profile_id=profile.id,
        )
        return _ScheduleResolution(
            availability, mapping if availability.enabled else None, response
        )

    @staticmethod
    def compatibility(
        mapping: ScheduleMapping, response: dict[str, Any]
    ) -> Literal["enabled", "retry", "incompatible"]:
        """Incomplete data takes precedence over conclusive incompatibilities."""
        outcomes = {
            _parameter_compatibility(response, getattr(mapping, name))
            for name in WEEKDAYS
        }
        if "retry" in outcomes:
            return "retry"
        if "incompatible" in outcomes:
            return "incompatible"
        return "enabled"

    async def probe_candidate(self, candidate_id: str) -> ScheduleCandidateProbe:
        """Read the bounded #1668 DHW candidate, never select or enable a profile."""
        if candidate_id != "issue_1668_dhw":
            raise BSBLANInvalidParameterError(candidate_id)
        self._guard()
        device = await self._device()
        self._guard()
        if device.bus not in {"BSB", "LPB"}:
            msg = "Schedule candidate probes require an explicit BSB or LPB bus"
            raise BSBLANUnsupportedFeatureError(msg)
        # Issue #1668 supplies these custom-table rows for family 211/variant 127.
        # They are not certified for this caller's active installation/table.
        mapping = ScheduleMapping(
            monday="561",
            tuesday="561.1",
            wednesday="561.2",
            thursday="561.3",
            friday="561.4",
            saturday="561.5",
            sunday="561.6",
        )
        params = tuple(getattr(mapping, name) for name in WEEKDAYS)
        response = await self._checked_request({"Parameter": ",".join(params)})
        outcomes = {
            param: _parameter_compatibility(response, param) for param in params
        }
        retry = tuple(param for param, status in outcomes.items() if status == "retry")
        incompatible = tuple(
            param for param, status in outcomes.items() if status == "incompatible"
        )
        status: Literal["retry", "incompatible", "compatible"] = "compatible"
        if retry:
            status = "retry"
        elif incompatible:
            status = "incompatible"
        return ScheduleCandidateProbe(
            candidate_id=candidate_id,
            evidence="https://github.com/liudger/python-bsblan/issues/1668",
            mapping=mapping,
            status=status,
            incompatible_parameters=incompatible,
            retry_parameters=retry,
        )
