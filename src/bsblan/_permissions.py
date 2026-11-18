"""Interpret parameter permissions separately from gateway default write flags."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


def read_write_permission(metadata: Mapping[str, Any]) -> bool | None:
    """Return explicit read/write permission, denial, or absent evidence.

    Firmware readwrite codes are 0=read/write, 1=read-only, 2=write-only.
    A legacy readonly=0 also permits a parameter whose value can be read.
    Contradictory, malformed or unknown flags never grant permission.
    """
    fields = ("readonly", "readwrite")
    present = [metadata[name] for name in fields if name in metadata]
    if not present:
        return None
    return all(type(value) is int and value == 0 for value in present)
