"""Tests for tolerant decoding of non-UTF-8 BSB-LAN responses."""

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig


@pytest.mark.asyncio
async def test_request_decodes_latin1_response(
    aresponses: ResponsesMockServer,
) -> None:
    """Latin-1 responses (e.g. custom descriptions with '§') are decoded."""
    # "§" is byte 0xa7 in Latin-1 and is an invalid UTF-8 start byte.
    payload = '{"700": {"name": "x", "desc": "Betrieb \u00a7", "value": "1"}}'
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=payload.encode("latin-1"),
        ),
    )

    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        response = await bsblan._request()

    assert response["700"]["desc"] == "Betrieb \u00a7"


@pytest.mark.asyncio
async def test_request_decodes_utf8_response(
    aresponses: ResponsesMockServer,
) -> None:
    """Valid UTF-8 responses keep decoding correctly."""
    payload = '{"700": {"name": "x", "desc": "Außentemperatur", "value": "1"}}'
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=payload.encode("utf-8"),
        ),
    )

    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        response = await bsblan._request()

    assert response["700"]["desc"] == "Außentemperatur"
