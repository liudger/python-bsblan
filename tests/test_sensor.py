"""Tests for retrieving information from the BSBLAN device."""
# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile
import asyncio

import aiohttp
import pytest

from bsblan import BSBLAN, Sensor

from . import load_fixture


@pytest.mark.asyncio
async def test_sensor(aresponses, mocker, monkeypatch):
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
        bsblan = BSBLAN(host="example.com", session=session)

        monkeypatch.setattr(bsblan, "_version", "1.0.38-20200730234859")

        future = asyncio.Future()
        future.set_result([8700, 8740])
        mocker.patch(
            # need to patch _scan
            "bsblan.BSBLAN._scan",
            return_value=future,
        )

        # await bsblan._scan(params)
        sensor: Sensor = await bsblan.sensor()
        assert sensor
        assert sensor.current_temperature.value == "18.2"
        assert sensor.outside_temperature.value == "7.6"
