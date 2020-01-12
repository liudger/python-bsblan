"""Tests for `bsblan.BSBLan`."""
import asyncio
import json

import aiohttp
import pytest
from bsblan import BSBLan
from bsblan.__version__ import __version__
from bsblan.exceptions import BSBLanConnectionError, BSBLanError

# from .models import State, Thermostat


# @pytest.mark.asyncio
# async def test_json_request(event_loop, aresponses):
#     """Test JSON response is handled correctly."""
#     assert State.from_dict == {
#         "current_havoc_mode" = 'Heizbetrieb Komfort',
#         "current_heatpump_mode" = 'Compressor 1 aan',
#         "current_target_temperature" = '19.0',
#         "current_temperature" = "18.6",
#         "temperature_unit" = '&deg;C')
# # return State


@pytest.mark.asyncio
async def test_json_request(event_loop, aresponses):
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
    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan("example.com", session=session, loop=event_loop)
        response = await bsblan._request("/JQ")
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_json_data_request(event_loop, aresponses):
    """Test JSON response is handled correctly."""

    aresponses.add(
        "example.com", "/JQ", "POST", aresponses.Response(status=200, text="OK"),
    )
    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan("example.com", session=session, loop=event_loop)
        response = await bsblan._request("/JQ", data=json.dumps(dict(foo="bar")),)
        assert response == "OK"


@pytest.mark.asyncio
async def test_json_data_send(event_loop, aresponses):
    """Test JSON response is handled correctly."""

    aresponses.add(
        "example.com", "/JS", "POST", aresponses.Response(status=200, text="OK"),
    )
    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan("example.com", session=session, loop=event_loop)
        # thermostat = await bsblan.thermostat(target_temperature=19.0)
        response = await bsblan._request(
            "/JS", data=json.dumps(dict(target_temperature=19.0)),
        )
        assert response == "OK"


@pytest.mark.asyncio
async def test_passkey_request(event_loop, aresponses):
    """Test JSON response is handled correctly."""
    aresponses.add(
        "example.com",
        "/",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        ),
    )
    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan(
            "example.com", passkey="1234", session=session, loop=event_loop,
        )
        response = await bsblan._request("/")
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_authenticated_request(event_loop, aresponses):
    """Test JSON response is handled correctly."""
    aresponses.add(
        "example.com",
        "/",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        ),
    )
    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan(
            "example.com",
            username="liudger",
            password="1234",
            session=session,
            loop=event_loop,
        )
        response = await bsblan._request("/")
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_text_request(event_loop, aresponses):
    """Test non JSON response is handled correctly."""
    aresponses.add(
        "example.com", "/", "Post", aresponses.Response(status=200, text="OK")
    )
    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan("example.com", session=session, loop=event_loop)
        response = await bsblan._request("/")
        assert response == "OK"


@pytest.mark.asyncio
async def test_internal_session(event_loop, aresponses):
    """Test JSON response is handled correctly."""
    aresponses.add(
        "example.com",
        "/",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        ),
    )
    async with BSBLan("example.com", loop=event_loop) as bsblan:
        response = await bsblan._request("/")
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_internal_eventloop(aresponses):
    """Test JSON response is handled correctly."""
    aresponses.add(
        "example.com",
        "/",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        ),
    )
    async with BSBLan("example.com") as bsblan:
        response = await bsblan._request("/")
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_post_request(event_loop, aresponses):
    """Test POST requests are handled correctly."""
    aresponses.add(
        "example.com", "/", "POST", aresponses.Response(status=200, text="OK")
    )
    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan("example.com", session=session, loop=event_loop)
        response = await bsblan._request("/", data={})
        assert response == "OK"


@pytest.mark.asyncio
async def test_request_port(event_loop, aresponses):
    """Test BSBLan running on non-standard port."""
    aresponses.add(
        "example.com:3333",
        "/",
        "POST",
        aresponses.Response(text="OMG PUPPIES!", status=200),
    )

    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan("example.com", port=3333, session=session, loop=event_loop)
        response = await bsblan._request("/")
        assert response == "OMG PUPPIES!"


@pytest.mark.asyncio
async def test_request_user_agent(event_loop, aresponses):
    """Test BSBLan client sending correct user agent headers."""
    # Handle to run asserts on request in
    async def response_handler(request):
        assert request.headers["User-Agent"] == f"PythonBSBLan/{__version__}"
        return aresponses.Response(text="TEDDYBEAR", status=200)

    aresponses.add("example.com", "/", "POST", response_handler)

    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan("example.com", session=session, loop=event_loop)
        await bsblan._request("/")


@pytest.mark.asyncio
async def test_request_custom_user_agent(event_loop, aresponses):
    """Test BSBLan client sending correct user agent headers."""
    # Handle to run asserts on request in
    async def response_handler(request):
        assert request.headers["User-Agent"] == "LoremIpsum/1.0"
        return aresponses.Response(text="TEDDYBEAR", status=200)

    aresponses.add("example.com", "/", "POST", response_handler)

    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan(
            "example.com",
            session=session,
            loop=event_loop,
            user_agent="LoremIpsum/1.0",
        )
        await bsblan._request("/")


@pytest.mark.asyncio
async def test_timeout(event_loop, aresponses):
    """Test request timeout from BSBLan."""
    # Faking a timeout by sleeping
    async def response_handler(_):
        await asyncio.sleep(2)
        return aresponses.Response(body="Goodmorning!")

    aresponses.add("example.com", "/", "POST", response_handler)

    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan(
            "example.com", session=session, loop=event_loop, request_timeout=1
        )
        with pytest.raises(BSBLanConnectionError):
            assert await bsblan._request("/")


@pytest.mark.asyncio
async def test_http_error400(event_loop, aresponses):
    """Test HTTP 404 response handling."""
    aresponses.add(
        "example.com", "/", "POST", aresponses.Response(text="OMG PUPPIES!", status=404)
    )

    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan("example.com", session=session, loop=event_loop)
        with pytest.raises(BSBLanError):
            assert await bsblan._request("/")


@pytest.mark.asyncio
async def test_http_error500(event_loop, aresponses):
    """Test HTTP 500 response handling."""
    aresponses.add(
        "example.com",
        "/",
        "POST",
        aresponses.Response(
            body=b'{"status":"nok"}',
            status=500,
            headers={"Content-Type": "application/json"},
        ),
    )

    async with aiohttp.ClientSession(loop=event_loop) as session:
        bsblan = BSBLan("example.com", session=session, loop=event_loop)
        with pytest.raises(BSBLanError):
            assert await bsblan._request("/")


# @pytest.mark.asyncio
# async def test_state_on(event_loop, aresponses):
#     """Test request of current BSBLan device state."""
#     aresponses.add(
#         "example.com",
#         "/json/",
#         "POST",
#         aresponses.Response(
#             status=200,
#             headers={"Content-Type": "application/json"},
#             text='{"state": {"on": true}}',
#         ),
#     )
#     aresponses.add(
#         "example.com",
#         "/json/",
#         "POST",
#         aresponses.Response(
#             status=200,
#             headers={"Content-Type": "application/json"},
#             text='{"state": {"on": false}}',
#         ),
#     )
#     async with aiohttp.ClientSession(loop=event_loop) as session:
#         bsblan = BSBLan("example.com", session=session, loop=event_loop)
#         device = await bsblan.update()
#         assert device.state.on
#         device = await bsblan.update()
#         assert not device.state.on
