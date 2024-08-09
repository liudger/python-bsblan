"""Tests for BSBLAN Library."""

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access
import asyncio
from typing import Any

import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.exceptions import BSBLANConnectionError, BSBLANError

from . import load_fixture


@pytest.mark.asyncio
async def test_json_request(aresponses: ResponsesMockServer) -> None:
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
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)
    response = await bsblan._request()
    assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_passkey_request(aresponses: ResponsesMockServer) -> None:
    """Test JSON response is handled correctly with passkey."""
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
    config = BSBLANConfig(host="example.com", passkey="1234")
    bsblan = BSBLAN(config)
    response = await bsblan._request()
    assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_authenticated_request(aresponses: ResponsesMockServer) -> None:
    """Test JSON response is handled correctly with authentication."""
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
    config = BSBLANConfig(
        host="example.com",
        username=load_fixture("password.txt"),
        password=load_fixture("password.txt"),
    )

    bsblan = BSBLAN(config)
    response = await bsblan._request()
    assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_internal_session(aresponses: ResponsesMockServer) -> None:
    """Test JSON response is handled correctly with internal session."""
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
    config = BSBLANConfig(host="example.com")
    async with BSBLAN(config) as bsblan:
        response = await bsblan._request()
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_connection_error(aresponses: ResponsesMockServer) -> None:
    """Test connection error is handled correctly."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(status=404, text="Not found"),
    )
    config = BSBLANConfig(host="example.com")

    bsblan = BSBLAN(config)
    with pytest.raises(BSBLANConnectionError):
        await bsblan._request()


@pytest.mark.asyncio
async def test_invalid_json(aresponses: ResponsesMockServer) -> None:
    """Test invalid JSON response is handled correctly."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"',
        ),
    )
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)
    with pytest.raises(BSBLANError):
        await bsblan._request()


@pytest.mark.asyncio
async def test_request_port(aresponses: ResponsesMockServer) -> None:
    """Test BSBLAN running on non-standard port."""
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

    config = BSBLANConfig(host="example.com", port=3333)

    bsblan = BSBLAN(config)
    response = await bsblan._request()
    assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_timeout(aresponses: ResponsesMockServer) -> None:
    """Test request timeout from BSBLAN."""

    # Faking a timeout by sleeping
    async def response_handler(_: Any) -> Any:
        await asyncio.sleep(2)
        return aresponses.Response(body="Goodmorning!")

    aresponses.add("example.com", "/JQ", "POST", response_handler)

    config = BSBLANConfig(host="example.com", request_timeout=2)
    bsblan = BSBLAN(config)
    with pytest.raises(BSBLANConnectionError):
        await bsblan._request()
    assert BSBLANConnectionError.message


@pytest.mark.asyncio
async def test_http_error404(aresponses: ResponsesMockServer) -> None:
    """Test HTTP 404 response handling."""
    aresponses.add(
        "example.com",
        "/",
        "POST",
        aresponses.Response(text="OMG PUPPIES!", status=404),
    )
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)
    with pytest.raises(BSBLANError):
        assert await bsblan._request("GET", "/")


@pytest.mark.asyncio
async def test_unexpected_response(aresponses: ResponsesMockServer) -> None:
    """Test unexpected response handling."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(text="OMG PUPPIES!", status=200),
    )
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)
    with pytest.raises(BSBLANError):
        assert await bsblan._request()


@pytest.mark.asyncio
async def test_not_authorized_401_response(aresponses: ResponsesMockServer) -> None:
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
    config = BSBLANConfig(
        host="example.com",
        username="user",
        password="pass",
    )
    bsblan = BSBLAN(config)
    with pytest.raises(BSBLANError):
        assert await bsblan._request("GET", "/JQ")
