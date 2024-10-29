"""Tests for scanning list of params from the BSBLAN device."""

# file deepcode ignore W0212: this is a testfile

from typing import TYPE_CHECKING

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig

from . import load_fixture

if TYPE_CHECKING:
    from bsblan.models import Device


@pytest.mark.asyncio
async def test_device(aresponses: ResponsesMockServer) -> None:
    """Test scan params BSBLAN."""
    aresponses.add(
        "example.com",
        "/JI",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("device.json"),
        ),
    )
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        # test _info and _device_params
        device: Device = await bsblan.device()
        assert device
        assert device.name == "BSB-LAN"
        assert device.version == "1.0.38-20200730234859"
        assert device.MAC == "00:80:41:19:69:90"
        assert device.uptime == 969402857
