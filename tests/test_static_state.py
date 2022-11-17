"""Tests for retrieving information from the BSBLAN device."""
# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

import aiohttp
import pytest

from bsblan import BSBLAN, StaticState

from . import load_fixture


@pytest.mark.asyncio
async def test_sensor(aresponses, monkeypatch):
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
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(host="example.com", session=session)

        monkeypatch.setattr(bsblan, "_version", "1.0.38-20200730234859")

        static: StaticState = await bsblan.static_values()
        assert static
        assert static.min_temp.value == "8.0"
        assert static.max_temp.value == "20.0"
        assert bsblan.min_temp == "8.0"
        assert bsblan.max_temp == "20.0"
