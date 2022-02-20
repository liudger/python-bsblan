"""Tests for scanning list of params from the BSBLAN device."""
# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access
import aiohttp
import pytest

from bsblan import BSBLAN

from . import load_fixture


@pytest.mark.asyncio
async def test_scan(aresponses):
    """Test scan params BSBLAN."""
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
        bsblan = BSBLAN(host="example.com", session=session)
        params = [700, 710, 711, 712, 714, 730, 900, 8000, 8740, 8749]
        scan = await bsblan._scan(params)
        assert scan
        assert scan == "700,710,711,712,714,730,800,900,8000,8740,8749"


@pytest.mark.asyncio
async def test_scan_pop_data(aresponses):
    """Test scan params BSBLAN and pop data."""
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
        bsblan = BSBLAN(host="example.com", session=session)
        params = [700, 701, 710, 711, 712, 714, 730, 800, 900, 8000, 8740, 8749]
        scan = await bsblan._scan(params)
        assert scan == "700,710,711,712,714,730,800,900,8000,8740,8749"
