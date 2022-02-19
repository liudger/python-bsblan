"""Tests for retrieving BSBLAN info Library."""
import asyncio

import aiohttp
import pytest

from bsblan import BSBLAN, Info

from . import load_fixture


@pytest.mark.asyncio
async def test_info(aresponses, mocker, monkeypatch):
    """Test getting BSBLAN device information."""
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
        bsblan = BSBLAN("example.com", session=session)

        monkeypatch.setattr(bsblan, "_version", "1.0.38-20200730234859")

        future = asyncio.Future()
        future.set_result("700,710,711,712,714,730,900,8000,8740,8749")
        mocker.patch(
            # need to patch _scan
            "bsblan.BSBLAN._scan",
            return_value=future,
        )

        info: Info = await bsblan.info()
        assert info
        assert info.controller_family.value == "211"
        assert info.controller_variant.value == "127"
        assert info.device_identification.value == "RVS21.831F/127"
