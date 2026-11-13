"""Synthetic HTTP boundary tests for the structured schedule reader."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, ScheduleReadMapping
from bsblan.exceptions import (
    BSBLANAuthError,
    BSBLANConnectionError,
    BSBLANMalformedResponseError,
)

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer

PROFILE = ScheduleReadMapping(
    monday="502",
    tuesday="502.1",
    wednesday="502.2",
    thursday="502.3",
    friday="502.4",
    saturday="502.5",
    sunday="502.6",
)
PARAMS = "502,502.1,502.2,502.3,502.4,502.5,502.6"


@pytest.mark.parametrize("body", ["null", "17", '["payload"]', "[]"])
@pytest.mark.parametrize(
    "group",
    [("heating", 1, 0), ("heating", 2, 20), ("hot_water", None, 40)],
)
@pytest.mark.parametrize("target", [("first.example", 500), ("second.example", 700)])
async def test_http_non_object_envelope_is_contextual(
    aresponses: ResponsesMockServer,
    body: str,
    group: tuple[str, int | None, int],
    target: tuple[str, int],
) -> None:
    """Classify JSON non-objects after the real firmware-5 transport path."""
    kind, circuit, offset = group
    host, base = target
    mapping = ScheduleReadMapping(
        **{day: str(base + offset + i) for i, day in enumerate(PROFILE.model_dump())}
    )
    params = ",".join(mapping.model_dump().values())
    calls: list[tuple[str, str, str | None]] = []

    async def handler(request: Any) -> Any:
        calls.append((request.method, request.path, request.query.get("Parameter")))
        return aresponses.Response(status=200, text=body)

    aresponses.add(host, "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host=host), session=session)
        client._firmware_version = "5.0.0"
        if kind == "heating":
            assert circuit is not None
            request = client.get_heating_schedule(circuit=circuit, mapping=mapping)
        else:
            request = client.get_hot_water_schedule(mapping=mapping)
        with pytest.raises(BSBLANMalformedResponseError) as exc:
            await request
        assert f"{kind} schedule circuit {circuit}" in str(exc.value)
        assert all(param in str(exc.value) for param in params.split(","))
        assert exc.value.__cause__ is None
    assert calls == [("POST", "/JQ", params)]


async def test_firmware_5_object_payload_is_removed(
    aresponses: ResponsesMockServer,
) -> None:
    """Only the debug payload is removed from a valid JSON object."""
    calls: list[tuple[str, str, str | None]] = []

    async def handler(request: Any) -> Any:
        calls.append((request.method, request.path, request.query.get("Parameter")))
        return aresponses.Response(text=json.dumps({"payload": "debug", "502": {}}))

    aresponses.add("example.com", "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._firmware_version = "5.0.0"
        result = await client._request(params={"Parameter": PARAMS})
    assert result == {"502": {}}
    assert calls == [("POST", "/JQ", PARAMS)]


@pytest.mark.parametrize(("path", "version"), [("/JQ", "4.9.9"), ("/JS", "5.0.0")])
async def test_payload_is_untouched_outside_firmware_5_jq(
    aresponses: ResponsesMockServer, path: str, version: str
) -> None:
    """Legacy firmware and writer endpoint preserve object payloads."""
    body = {"payload": "debug", "502": {}}
    aresponses.add(
        "example.com", path, "POST", aresponses.Response(text=json.dumps(body))
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._firmware_version = version
        result = await client._request(base_path=path)
    assert result == body


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, "", BSBLANAuthError),
        (403, "", BSBLANAuthError),
        (404, "", BSBLANConnectionError),
        (200, "not-json", BSBLANMalformedResponseError),
    ],
)
async def test_http_errors_are_not_reclassified(
    aresponses, status, body, error
) -> None:
    """Preserve transport errors and make exactly one synthetic request."""
    calls = []

    async def handler(request: Any) -> Any:
        calls.append((request.method, request.path, request.query.get("Parameter")))
        return aresponses.Response(status=status, text=body)

    aresponses.add("example.com", "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        with pytest.raises(error) as exc:
            await client.get_heating_schedule(mapping=PROFILE)
        assert exc.value.__cause__ is not None
    assert calls == [("POST", "/JQ", PARAMS)]


async def test_http_success_and_exact_query(aresponses: ResponsesMockServer) -> None:
    """Send the seven explicit IDs to the existing HTTP endpoint."""
    calls: list[tuple[str, str, str | None]] = []

    async def handler(request: Any) -> Any:
        calls.append((request.method, request.path, request.query.get("Parameter")))
        return aresponses.Response(
            text=json.dumps(
                {
                    "502": {
                        "name": "x",
                        "value": "06:00-07:00",
                        "unit": "",
                        "desc": "",
                        "error": 0,
                        "dataType": 9,
                    }
                }
            )
        )

    aresponses.add("example.com", "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        result = await client.get_heating_schedule(mapping=PROFILE)
    assert result.days["monday"].status == "readable"
    assert result.days["tuesday"].status == "unavailable"
    assert calls == [("POST", "/JQ", PARAMS)]


async def test_http_timeout_uses_bounded_existing_retry(
    aresponses: ResponsesMockServer,
) -> None:
    """Transport timeout uses exactly the existing three attempts."""
    calls: list[tuple[str, str, str | None]] = []

    async def handler(request: Any) -> Any:
        calls.append((request.method, request.path, request.query.get("Parameter")))
        await asyncio.sleep(0.1)
        return aresponses.Response(text="{}")

    for _ in range(3):
        aresponses.add("example.com", "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(
            BSBLANConfig(host="example.com", request_timeout=0.01), session=session
        )
        with pytest.raises(BSBLANConnectionError) as exc:
            await client.get_heating_schedule(mapping=PROFILE)
        assert exc.value.__cause__ is not None
    assert calls == [("POST", "/JQ", PARAMS)] * 3


async def test_connection_error_uses_bounded_existing_retry() -> None:
    """A synthetic connection failure remains a connection error after retries."""
    async with aiohttp.ClientSession() as session:
        request = Mock(side_effect=aiohttp.ClientConnectionError("synthetic"))
        session.request = request
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        with pytest.raises(BSBLANConnectionError) as exc:
            await client.get_heating_schedule(mapping=PROFILE)
        assert isinstance(exc.value.__cause__, aiohttp.ClientConnectionError)
    assert request.call_count == 3
    assert all(call.args[0] == "POST" for call in request.call_args_list)
    assert all(call.args[1].path == "/JQ" for call in request.call_args_list)
    assert all(
        call.kwargs["params"] == {"Parameter": PARAMS}
        for call in request.call_args_list
    )
