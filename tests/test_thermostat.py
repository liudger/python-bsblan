"""Tests for sending values to the BSBLAN device."""

import aiohttp
import pytest

from bsblan import BSBLAN

from . import load_fixture


@pytest.mark.asyncio
async def test_change_temperature(aresponses):
    """Test changing BSBLAN temperature."""

    async def response_handler(request):
        data = await request.json()
        assert data == {"Parameter": "710", "Value": "19", "Type": "1"}

        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("thermostat_temp.json"),
        )

    aresponses.add("example.com", "/JS", "POST", response_handler)

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN("example.com", session=session)
        await bsblan.thermostat(target_temperature="19")


@pytest.mark.asyncio
async def test_change_preset_mode(aresponses):
    """Test changing BSBLAN preset mode."""

    async def response_handler(request):
        data = await request.json()
        assert data == {"Parameter": "700", "EnumValue": 3, "Type": "1"}

        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("thermostat_preset.json"),
        )

    aresponses.add("example.com", "/JS", "POST", response_handler)

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN("example.com", session=session)
        await bsblan.thermostat(preset_mode="comfort")
