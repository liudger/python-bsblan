"""Tests for BSBLan Library."""
# file deepcode ignore W0212: this is a testfile
import asyncio

import aiohttp
import pytest
from bsblan import BSBLan
from bsblan.exceptions import BSBLanConnectionError, BSBLanError


@pytest.mark.asyncio
async def test_json_request(aresponses):
    """Test JSON response is handled correctly."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        ),
    )
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan(host="example.com", session=session)
        response = await bsblan._request()
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_passkey_request(aresponses):
    """Test JSON response is handled correctly."""
    aresponses.add(
        "example.com",
        "/1234/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        ),
    )
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan(host="example.com", session=session, passkey="1234")
        response = await bsblan._request()
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_authenticated_request(aresponses):
    """Test JSON response is handled correctly."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        ),
    )
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan(
            "example.com",
            username="liudger",
            password="1234",
            session=session,
        )
        response = await bsblan._request()
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_internal_session(aresponses):
    """Test JSON response is handled correctly."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        ),
    )
    async with BSBLan("example.com") as bsblan:
        response = await bsblan._request()
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_request_port(aresponses):
    """Test BSBLan running on non-standard port."""
    aresponses.add(
        "example.com:3333",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        ),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan("example.com", port=3333, session=session)
        response = await bsblan._request()
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_timeout(aresponses):
    """Test request timeout from BSBLan."""
    # Faking a timeout by sleeping
    async def response_handler(_):
        await asyncio.sleep(2)
        return aresponses.Response(body="Goodmorning!")

    aresponses.add("example.com", "/JQ", "POST", response_handler)

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan("example.com", session=session, request_timeout=2)
        with pytest.raises(BSBLanConnectionError):
            assert await bsblan._request()


@pytest.mark.asyncio
async def test_http_error400(aresponses):
    """Test HTTP 404 response handling."""
    aresponses.add(
        "example.com", "/", "POST", aresponses.Response(text="OMG PUPPIES!", status=404)
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan("example.com", session=session)
        with pytest.raises(BSBLanError):
            assert await bsblan._request("/")


@pytest.mark.asyncio
async def test_unexpected_response(aresponses):
    """Test unexpected response handling."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(text="OMG PUPPIES!", status=200),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan("example.com", session=session)
        with pytest.raises(BSBLanError):
            assert await bsblan._request()


@pytest.mark.asyncio
async def test_not_authorized_401_response(aresponses):
    """Test wrong username and password response handling."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=401,
            headers={"Content-Type": "text/html"},
        ),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan("example.com", session=session)
        with pytest.raises(BSBLanError):
            response = await bsblan._request("/JQ")
            assert response.status == 401
