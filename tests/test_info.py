"""Tests for retrieving BSBLan info Library."""
import aiohttp
import pytest
from bsblan import BSBLan, Info

from . import load_fixture


@pytest.mark.asyncio
async def test_info(aresponses):
    """Test getting BSBLan device information."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("info.json"),
        ),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan("example.com", session=session)
        info: Info = await bsblan.info()
        assert info
        assert info.controller_family == "211"
        assert info.controller_variant == "127"
        assert info.device_identification == "RVS21.831F/127"
