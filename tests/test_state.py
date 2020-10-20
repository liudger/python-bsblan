"""Tests for retreiving information from the BSBLan device."""
import asyncio

import aiohttp
import pytest
from bsblan import BSBLan, State

from . import load_fixture


@pytest.mark.asyncio
async def test_state(aresponses, mocker):
    """Test getting BSBLan state."""
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
        bsblan = BSBLan(host="example.com", session=session)
        future = asyncio.Future()
        future.set_result("700,710,711,712,714,730,900,8000,8740,8749")
        mocker.patch(
            # need to patch _scan
            "bsblan.BSBLan._scan",
            return_value=future,
        )
        # await bsblan._scan(params)
        state: State = await bsblan.state()
        assert state
        assert state.hvac_mode.name == "Operating mode"
        assert state.hvac_mode.value == "3"
        assert state.current_temperature.value == "19.5"
