"""Tests for retrieving information from the BSBLAN device."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from typing import Any

import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig, StaticState

from . import load_fixture


@pytest.mark.asyncio
async def test_sensor(aresponses: ResponsesMockServer, monkeypatch: Any) -> None:
    """Test getting BSBLAN state."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("static_state.json"),
        ),
    )
    bsblan = BSBLAN(config=BSBLANConfig(host="example.com"))

    monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")

    static: StaticState = await bsblan.static_values()
    assert static
    assert static.min_temp.value == "8.0"
    assert static.max_temp.value == "20.0"
    assert bsblan._min_temp == "8.0"
    assert bsblan._max_temp == "20.0"
