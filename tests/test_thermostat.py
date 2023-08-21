"""Tests for sending values to the BSBLAN device."""

from typing import Any

import aiohttp
import pytest
from aresponses import Response, ResponsesMockServer

from bsblan import BSBLAN

from . import load_fixture


@pytest.mark.asyncio
async def test_change_temperature(aresponses: ResponsesMockServer) -> None:
    """Test changing BSBLAN temperature."""

    async def response_handler(request: Any) -> Response:
        data = await request.json()
        assert data == {"Parameter": "710", "Value": "19", "Type": "1"}

        return Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("thermostat_temp.json"),
        )

    aresponses.add("example.com", "/JS", "POST", response_handler)

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN("example.com", session=session)
        await bsblan.thermostat(target_temperature="19")


@pytest.mark.asyncio
async def test_change_hvac_mode(aresponses: ResponsesMockServer) -> None:
    """Test changing BSBLAN hvac mode."""

    async def response_handler(request: Any) -> Response:
        data = await request.json()
        assert data == {"Parameter": "700", "EnumValue": 3, "Type": "1"}

        return Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("thermostat_hvac.json"),
        )

    aresponses.add("example.com", "/JS", "POST", response_handler)

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN("example.com", session=session)
        await bsblan.thermostat(hvac_mode="heat")
