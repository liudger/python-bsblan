"""Tests for retrieving information from the BSBLAN device."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from typing import Any

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig, Sensor

from . import load_fixture


@pytest.mark.asyncio
async def test_sensor(aresponses: ResponsesMockServer, monkeypatch: Any) -> None:
    """Test getting BSBLAN state."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("sensor.json"),
        ),
    )
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        # set _api_version
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        sensor: Sensor = await bsblan.sensor()
        assert sensor
        assert sensor.current_temperature.value == "18.2"
        assert sensor.outside_temperature.value == "7.6"
