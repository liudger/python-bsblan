"""Tests for retrieving BSBLAN info Library."""
# file deepcode ignore W0212: this is a testfile

from typing import Any

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN, Info

from . import load_fixture


@pytest.mark.asyncio
async def test_info(aresponses: ResponsesMockServer, monkeypatch: Any) -> None:
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
    )  # disable=duplicate-code
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN("example.com", session=session)

        monkeypatch.setattr(bsblan, "_version", "1.0.38-20200730234859")

        info: Info = await bsblan.info()
        assert info
        assert info.controller_family.value == "211"
        assert info.controller_variant.value == "127"
        assert info.device_identification.value == "RVS21.831F/127"
