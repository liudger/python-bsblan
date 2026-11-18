"""Match a predefined source-backed schedule layout, never infer weekday roles."""

from __future__ import annotations

from typing import Any, Literal

from .exceptions import BSBLANMalformedResponseError
from .models import DataType

TableStatus = Literal["match", "retry", "incompatible"]
type TableKey = tuple[tuple[tuple[str, str], ...], int]


def table_status(
    response: dict[str, Any], expected: tuple[tuple[str, str], ...], destination: int
) -> TableStatus:
    """Require every declared name/type/destination; incomplete data takes priority."""
    outcomes: set[TableStatus] = set()
    for param, name in expected:
        if param not in response:
            outcomes.add("retry")
            continue
        raw = response[param]
        if not isinstance(raw, dict) or (
            "error" in raw and type(raw["error"]) is not int
        ):
            msg = f"Invalid schedule table structure for {param}"
            raise BSBLANMalformedResponseError(msg)
        if raw.get("error") == 7:
            outcomes.add("incompatible")
        elif raw.get("error") or any(
            raw.get(field) is None for field in ("name", "dataType", "destination")
        ):
            outcomes.add("retry")
        elif (
            raw["name"] != name
            or type(raw["dataType"]) is not int
            or raw["dataType"] != DataType.TIMEPROG
            or type(raw["destination"]) is not int
            or raw["destination"] != destination
        ):
            outcomes.add("incompatible")
        else:
            outcomes.add("match")
    return (
        "retry"
        if "retry" in outcomes
        else "incompatible"
        if "incompatible" in outcomes
        else "match"
    )
