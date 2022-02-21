"""Tests for retrieving information from the BSBLAN device."""
# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile
import asyncio

import aiohttp
import pytest

from bsblan import BSBLAN, State

from . import load_fixture


@pytest.mark.asyncio
async def test_state(aresponses, mocker, monkeypatch):
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
    )  # noqa R0801
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(host="example.com", session=session)

        monkeypatch.setattr(bsblan, "_version", "1.0.38-20200730234859")

        future = asyncio.Future()
        future.set_result("700,710,711,712,714,730,900,8000,8700,8740,8749")
        mocker.patch(
            # need to patch _scan
            "bsblan.BSBLAN._scan",
            return_value=future,
        )

        # await bsblan._scan(params)
        state: State = await bsblan.state()
        assert state
        assert state.hvac_mode.name == "Operating mode"
        assert state.hvac_mode.value == "3"
        assert state.current_temperature.value == "18.2"
