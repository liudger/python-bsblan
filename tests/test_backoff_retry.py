"""Tests for exponential backoff retry logic in BSBLAN."""

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access

import asyncio
from typing import Any

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.exceptions import BSBLANConnectionError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_status", "error_text", "fail_count"),
    [
        pytest.param(500, "Internal Server Error", 2, id="500_twice_then_success"),
        pytest.param(502, "Bad Gateway", 1, id="502_once_then_success"),
        pytest.param(503, "Service Unavailable", 1, id="503_once_then_success"),
    ],
)
async def test_retry_on_transient_error(
    aresponses: ResponsesMockServer,
    error_status: int,
    error_text: str,
    fail_count: int,
) -> None:
    """Test that transient HTTP errors are retried and succeed on retry."""
    # Add failing responses
    for _ in range(fail_count):
        aresponses.add(
            "example.com",
            "/JQ",
            "POST",
            aresponses.Response(status=error_status, text=error_text),
        )
    # Add successful response
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
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        response = await bsblan._request()
        assert response["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_statuses",
    [
        pytest.param([500, 502], id="500_then_502_then_success"),
        pytest.param([503, 500], id="503_then_500_then_success"),
    ],
)
async def test_retry_mixed_errors(
    aresponses: ResponsesMockServer,
    error_statuses: list[int],
) -> None:
    """Test mixed transient errors are all retried."""
    error_texts = {
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
    }
    # Add failing responses
    for status in error_statuses:
        aresponses.add(
            "example.com",
            "/JQ",
            "POST",
            aresponses.Response(status=status, text=error_texts[status]),
        )
    # Add successful response
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
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        response = await bsblan._request()
        assert response["status"] == "ok"


@pytest.mark.asyncio
async def test_retry_respects_max_tries(aresponses: ResponsesMockServer) -> None:
    """Test that retry stops after max_tries (3) attempts."""
    # All 3 requests fail with 500
    for _ in range(3):
        aresponses.add(
            "example.com",
            "/JQ",
            "POST",
            aresponses.Response(status=500, text="Internal Server Error"),
        )

    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        with pytest.raises(BSBLANConnectionError):
            await bsblan._request()


@pytest.mark.asyncio
async def test_no_retry_on_404_giveup(aresponses: ResponsesMockServer) -> None:
    """Test that 404 errors are not retried (giveup condition)."""
    # Only one request - 404 should not retry
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(status=404, text="Not Found"),
    )

    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        with pytest.raises(BSBLANConnectionError):
            await bsblan._request()


@pytest.mark.asyncio
async def test_retry_on_timeout_error(aresponses: ResponsesMockServer) -> None:
    """Test that timeout errors are retried."""
    call_count = 0

    async def timeout_then_success(_: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            # Simulate timeout by sleeping longer than request timeout
            await asyncio.sleep(2)
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text='{"status": "ok"}',
        )

    # Add handlers for potential retries
    aresponses.add("example.com", "/JQ", "POST", timeout_then_success)
    aresponses.add("example.com", "/JQ", "POST", timeout_then_success)
    aresponses.add("example.com", "/JQ", "POST", timeout_then_success)

    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com", request_timeout=1)
        bsblan = BSBLAN(config, session=session)
        response = await bsblan._request()
        assert response["status"] == "ok"
        assert call_count == 3


@pytest.mark.asyncio
async def test_timeout_error_exhausts_retries(aresponses: ResponsesMockServer) -> None:
    """Test that TimeoutError is raised after all retries are exhausted."""

    async def always_timeout(_: Any) -> Any:
        # Always timeout
        await asyncio.sleep(2)
        return aresponses.Response(status=200, text="Never reached")

    # Add handlers for all 3 retry attempts
    aresponses.add("example.com", "/JQ", "POST", always_timeout)
    aresponses.add("example.com", "/JQ", "POST", always_timeout)
    aresponses.add("example.com", "/JQ", "POST", always_timeout)

    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com", request_timeout=1)
        bsblan = BSBLAN(config, session=session)
        with pytest.raises(BSBLANConnectionError):
            await bsblan._request()


@pytest.mark.asyncio
async def test_successful_request_no_retry(aresponses: ResponsesMockServer) -> None:
    """Test that successful requests don't trigger any retries."""
    # Single successful request
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
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        response = await bsblan._request()
        assert response["status"] == "ok"
