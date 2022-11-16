"""Tests for retrieving BSBLAN info Library."""
# file deepcode ignore W0212: this is a testfile
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
    )  # disable=duplicate-code
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN("example.com", session=session)

        monkeypatch.setattr(bsblan, "_version", "1.0.38-20200730234859")

        future = asyncio.Future()
        future.set_result([6224, 6225, 6226])
        # patch _scan
        mocker.patch("bsblan.BSBLAN._scan", return_value=future)

        # future2 = asyncio.Future()
        # future2.set_result((load_fixture("dict_version.json")))
        # mocker.patch("bsblan.BSBLAN._get_dict_version", return_value=future2)

        # future3 = asyncio.Future()
        # future3.set_result(({"string_par": "6224,6225,6226", "list": ["device_identification", "controller_family", "controller_variant"]}))
        # mocker.patch("bsblan.BSBLAN._get_parameters", return_value=future3)


        info: Info = await bsblan.info()
        assert info
        assert info.controller_family.value == "211"
        assert info.controller_variant.value == "127"
        assert info.device_identification.value == "RVS21.831F/127"
