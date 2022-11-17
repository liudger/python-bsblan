"""Tests for retrieving information from the BSBLAN device."""
# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

import aiohttp
import pytest

from bsblan import BSBLAN, State

from . import load_fixture


@pytest.mark.asyncio
async def test_state(aresponses, monkeypatch):
    """Test getting BSBLAN state."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("state.json"),
        ),
    )
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(host="example.com", session=session)

        monkeypatch.setattr(bsblan, "_version", "1.0.38-20200730234859")

        state: State = await bsblan.state()
        assert state
        assert state.hvac_mode.name == "Operating mode"
        assert state.hvac_mode.value == "heat"
        assert state.current_temperature.value == "18.4"
