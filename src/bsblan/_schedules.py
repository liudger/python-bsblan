"""Configured heating and hot-water schedule reads and sequential writes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from .constants import ErrorMsg
from .exceptions import (
    BSBLANError,
    BSBLANInvalidParameterError,
    BSBLANMalformedResponseError,
    BSBLANScheduleMappingError,
    BSBLANScheduleWriteError,
    BSBLANUnsupportedFeatureError,
)
from .models import DataType
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
    """Use one caller-confirmed mapping for both schedule reads and writes."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        request: Callable[..., Awaitable[dict[str, Any]]],
        set_payload: Callable[[str, str], dict[str, Any]],
        uses_pps_bus: Callable[[], bool],
        mappings: ScheduleMappings,
        bus_writable: Callable[[], bool],
        target_key: Callable[[], tuple[str, int, str | None]],
    ) -> None:
        """Capture validated mappings while resolving current transport/metadata."""
        self._request = request
        self._set_payload = set_payload
        self._uses_pps_bus = uses_pps_bus
        self._mappings = ScheduleMappings.model_validate(mappings)
        self._bus_writable = bus_writable
        self._target_key = target_key
        self._confirmed_target = target_key()

    def _mapping(
        self, kind: Literal["hot_water", "heating"], circuit: int | None
    ) -> ScheduleMapping:
        """Resolve the same immutable target mapping for reads and writes."""
        if kind == "heating" and (type(circuit) is not int or circuit not in (1, 2)):
            msg = f"circuit {circuit}"
            raise BSBLANInvalidParameterError(msg)
        if self._uses_pps_bus():
            msg = f"{kind} circuit {circuit}: PPS schedules unsupported"
            raise BSBLANUnsupportedFeatureError(msg)
        if self._target_key() != self._confirmed_target:
            raise BSBLANScheduleMappingError(kind, circuit, "target_changed")
        key = "hot_water" if kind == "hot_water" else f"heating_{circuit}"
        mapping = getattr(self._mappings, key)
        if mapping is None:
            raise BSBLANScheduleMappingError(kind, circuit, "mapping_unknown")
        return mapping

    async def read(
        self, kind: Literal["hot_water", "heating"], circuit: int | None = None
    ) -> ScheduleSnapshot:
        """Fetch all configured day IDs without availability caching."""
        mapping = self._mapping(kind, circuit)
        days = {name: getattr(mapping, name) for name in WEEKDAYS}
        context = (
            f"Invalid {kind} schedule circuit {circuit} "
            f"response for IDs {list(days.values())}"
        )
        try:
            response = await self._request(
                params={"Parameter": ",".join(days.values())}
            )
        except BSBLANMalformedResponseError as err:
            err.message = f"{context}: {err}"
            err.args = (err.message,)
            raise
        if not isinstance(response, dict):
            raise BSBLANMalformedResponseError(context)
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

    async def write(
        self,
        kind: Literal["hot_water", "heating"],
        update: ScheduleUpdate,
        circuit: int | None = None,
    ) -> None:
        """Prevalidate every day, then stop at the first uncertain/rejected write."""
        mapping = self._mapping(kind, circuit)
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
        if not self._bus_writable():
            msg = "Schedule writes are disabled on this bus"
            raise BSBLANUnsupportedFeatureError(msg)
        acknowledged: list[Weekday] = []
        for index, (name, param, value) in enumerate(commands):
            pending = tuple(command[0] for command in commands[index + 1 :])
            try:
                self._mapping(kind, circuit)
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
