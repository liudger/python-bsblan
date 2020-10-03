"""Tests for BSBLan Library."""
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
        bsblan = BSBLan("example.com", session=session)
        response = await bsblan._request("/JQ")
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_passkey_request(aresponses):
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
        bsblan = BSBLan("example.com", passkey="1234", session=session,)
        response = await bsblan._request("/JQ")
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
            "example.com", username="liudger", password="1234", session=session,
        )
        response = await bsblan._request("/JQ")
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
        response = await bsblan._request("/JQ")
        assert response["status"] == "ok"


# @pytest.mark.asyncio
# async def test_internal_eventloop(aresponses):
#     """Test JSON response is handled correctly."""
#     aresponses.add(
#         "example.com",
#         "/JQ",
#         "POST",
#         aresponses.Response(
#             status=200,
#             headers={"Content-Type": "application/json"},
#             text='{"status": "ok"}',
#         ),
#     )
#     async with BSBLan("example.com") as bsblan:
#         response = await bsblan._request("/JQ")
#         assert response["status"] == "ok"


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
        response = await bsblan._request("/JQ")
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
        bsblan = BSBLan("example.com", session=session, request_timeout=1)
        with pytest.raises(BSBLanConnectionError):
            assert await bsblan._request("/JQ")


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
async def test_http_error500(aresponses):
    """Test HTTP 500 response handling."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            body='{"status":"ok"}',
            status=500,
            headers={"Content-Type": "application/json"},
        ),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLan("example.com", session=session)
        with pytest.raises(BSBLanError):
            assert await bsblan._request("/JQ")


# @pytest.mark.asyncio
# async def test_unexpected_response(event_loop, aresponses):
#     """Test unexpected response handling."""
#     aresponses.add(
#         "example.com",
#         "/",
#         "POST",
#         aresponses.Response(
#             text="OMG PUPPIES!",
#             status=200),
#     )

#     async with aiohttp.ClientSession(loop=event_loop) as session:
#         bsblan = BSBLan("example.com", session=session, loop=event_loop)
#         with pytest.raises(BSBLanConnectionError):
#             assert await bsblan._request("/JQ")
