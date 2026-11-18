"""Match a predefined source-backed schedule layout, never infer weekday roles."""

from __future__ import annotations

from typing import Any, Literal

from .exceptions import BSBLANMalformedResponseError
from .models import DataType

TableStatus = Literal["match", "retry", "incompatible"]
type TableKey = tuple[tuple[tuple[str, str], ...], int]


def _parameter_table_status(
    response: dict[str, Any], param: str, name: str, destination: int
) -> TableStatus:
    """Classify one declared row while retaining malformed-response failures."""
    if param not in response:
        return "retry"
    raw = response[param]
    if not isinstance(raw, dict) or ("error" in raw and type(raw["error"]) is not int):
        msg = f"Invalid schedule table structure for {param}"
        raise BSBLANMalformedResponseError(msg)
    if raw.get("error") == 7:
        return "incompatible"
    if raw.get("error") or any(
        raw.get(field) is None for field in ("name", "dataType", "destination")
    ):
        return "retry"
    if (
        raw["name"] != name
        or type(raw["dataType"]) is not int
        or raw["dataType"] != DataType.TIMEPROG
        or type(raw["destination"]) is not int
        or raw["destination"] != destination
    ):
        return "incompatible"
    return "match"


def table_status(
    response: dict[str, Any], expected: tuple[tuple[str, str], ...], destination: int
) -> TableStatus:
    """Require every declared row and preserve incomplete-data priority."""
    outcomes = {
        _parameter_table_status(response, param, name, destination)
        for param, name in expected
    }
    if "retry" in outcomes:
        return "retry"
    if "incompatible" in outcomes:
        return "incompatible"
    return "match"
