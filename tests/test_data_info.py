"""Tests for scanning list of params from the BSBLAN device."""
# file deepcode ignore W0212: this is a testfile
import asyncio

import aiohttp
import pytest

from bsblan import BSBLAN


@pytest.mark.asyncio
async def test_scan_v1(aresponses, mocker, monkeypatch):
    """Test scan params BSBLAN."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
        ),
    )
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(host="example.com", session=session)

        # set _version
        monkeypatch.setattr(bsblan, "_version", "1.0.38-20200730234859")
        # patch scan
        future = asyncio.Future()
        future.set_result("6224,6225,6226")
        mocker.patch(
            # need to patch _scan
            "bsblan.BSBLAN._scan",
            return_value=future,
        )
        # test _info and _device_params

        await bsblan._get_data_info()
        assert bsblan._info == future
        assert bsblan._device_params == [
            "device_identification",
            "controller_family",
            "controller_variant",
        ]
