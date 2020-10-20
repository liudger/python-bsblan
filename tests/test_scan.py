"""Tests for scanning list of params from the BSBLan device."""
# file deepcode ignore W0212: this is a testfile
import aiohttp
import pytest
from bsblan import BSBLan

from . import load_fixture


@pytest.mark.asyncio
async def test_scan(aresponses):
    """Test scan params BSBLan."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("scan.json"),
        ),
    )
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan(host="example.com", session=session)
        params = [700, 710, 711, 712, 714, 730, 900, 8000, 8740, 8749]
        scan = await bsblan._scan(params)
        assert scan
        # assert state.hvac_mode.name == "Operating mode"
        # assert state.hvac_mode.value == "3"
