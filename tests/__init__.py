"""Asynchronous Python client for BSBLan."""

from pathlib import Path


def load_fixture(filename: str) -> str:
    """Load a fixture."""
    path = Path(__file__).parent / "fixtures" / filename
    with path.open(encoding="utf-8") as fptr:
        return fptr.read()
