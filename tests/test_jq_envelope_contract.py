"""Synthetic /JQ object boundaries, contextual decode causes, and recovery."""

from __future__ import annotations

import json
import pickle
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, ScheduleMapping, ScheduleMappings
from bsblan.exceptions import (
    BSBLANAuthError,
    BSBLANConnectionError,
    BSBLANMalformedResponseError,
)

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer

PROFILE = ScheduleMapping(
    monday="501",
    tuesday="502",
    wednesday="503",
    thursday="504",
    friday="505",
    saturday="506",
    sunday="507",
)
PARAMS = "501,502,503,504,505,506,507"


def configured() -> BSBLANConfig:
    """Use explicit synthetic profiles for every transport-tested schedule route."""
    return BSBLANConfig(
        host="example.com",
        schedule_mappings=ScheduleMappings(
            hot_water=PROFILE, heating_1=PROFILE, heating_2=PROFILE
        ),
    )


@pytest.mark.parametrize("firmware", [None, "4.9.9", "5.0.0"])
@pytest.mark.parametrize(
    "body", ['["payload"]', "[]", "null", "17", "false", '"secret-response"']
)
@pytest.mark.parametrize("route", ["parameters", "heating", "hot_water", "device"])
async def test_legacy_rejects_malformed_then_recovers(
    aresponses: ResponsesMockServer, firmware: str | None, body: str, route: str
) -> None:
    """Malformed envelopes never poison validation or schedule availability."""
    calls: list[tuple[str, str, str]] = []

    async def handler(request: Any) -> Any:
        params = request.query["Parameter"]
        calls.append((request.method, request.path, params))
        if len(calls) == 1:
            return aresponses.Response(text=body)
        entities = {
            param: {
                "name": "x",
                "value": "06:00-07:00",
                "unit": "",
                "desc": "",
                "error": 0,
                "dataType": 9,
            }
            for param in params.split(",")
        }
        return aresponses.Response(text=json.dumps(entities))

    aresponses.add("example.com", "/JQ", "POST", handler, repeat=2)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(configured(), session=session)
        client._firmware_version = firmware
        client._supports_full_config = True
        await client._setup_api_validator()
        assert client._api_data is not None
        original = dict(client._api_data["device"])
        validator = client._validator

        async def read() -> Any:
            if route == "parameters":
                return await client.read_parameters(["501"])
            if route == "heating":
                return await client.heating_schedule()
            if route == "hot_water":
                return await client.hot_water_schedule()
            return await client._ensure_section_validated("device")

        with pytest.raises(BSBLANMalformedResponseError) as exc:
            await read()
        assert "secret-response" not in str(exc.value)
        assert client._api_data["device"] == original
        assert not validator._api_validator.is_section_validated("device")
        assert not validator._validated_hot_water_groups
        assert not validator._validated_hot_water_parameters
        assert not validator.hot_water_param_cache
        assert len(calls) == 1
        result = await read()
        assert len(calls) == 2
        assert calls[0] == calls[1]
        if route == "parameters":
            assert result["501"].value == "06:00-07:00"
        elif route in {"heating", "hot_water"}:
            assert result.day("monday").raw_value == "06:00-07:00"
            assert result.complete
            assert not validator._validated_hot_water_groups
        else:
            assert client._api_data["device"] == original
            assert validator._api_validator.is_section_validated("device")


@pytest.mark.parametrize("firmware", [None, "4.9.9", "5.0.0"])
async def test_empty_object_is_valid_but_not_an_empty_week(
    aresponses: ResponsesMockServer, firmware: str | None
) -> None:
    """An empty object denotes missing days, never seven empty schedules."""
    aresponses.add("example.com", "/JQ", "POST", aresponses.Response(text="{}"))
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(configured(), session=session)
        client._firmware_version = firmware
        result = await client.heating_schedule()
    assert not result.complete
    assert all(
        day.status == "unavailable" and day.schedule is None for day in result.days
    )


@pytest.mark.parametrize("path", ["/JS", "/JV", "/JI"])
async def test_non_jq_non_object_is_unchanged(
    aresponses: ResponsesMockServer, path: str
) -> None:
    """/JQ object validation is not imposed on unrelated endpoints."""
    aresponses.add("example.com", path, "POST", aresponses.Response(text='["payload"]'))
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(configured(), session=session)
        client._firmware_version = "5.0.0"
        assert await client._request(base_path=path) == ["payload"]


@pytest.mark.parametrize("group", [("heating", 1), ("heating", 2), ("hot_water", None)])
async def test_decode_error_has_context_and_original_cause(
    aresponses: ResponsesMockServer, group: tuple[str, int | None]
) -> None:
    """Real JSON decode errors keep their details, cause, and schedule context."""
    calls = []

    async def handler(request: Any) -> Any:
        calls.append(request.query["Parameter"])
        return aresponses.Response(text="{bad")

    aresponses.add("example.com", "/JQ", "POST", handler)
    kind, circuit = group
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(configured(), session=session)
        client._firmware_version = "5.0.0"
        request = (
            client.heating_schedule(circuit=circuit)
            if kind == "heating"
            else client.hot_water_schedule()
        )
        with pytest.raises(BSBLANMalformedResponseError) as exc:
            await request
        assert isinstance(exc.value.__cause__, json.JSONDecodeError)
        assert "line 1" in str(exc.value)
        assert f"{kind} schedule circuit {circuit}" in str(exc.value)
        assert all(param in str(exc.value) for param in PARAMS.split(","))
    assert calls == [PARAMS]


async def test_existing_partial_device_validation_survives_malformed(
    aresponses: ResponsesMockServer,
) -> None:
    """A subsequent malformed validation cannot clear previously validated IDs."""
    aresponses.add("example.com", "/JQ", "POST", aresponses.Response(text="[]"))
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(configured(), session=session)
        client._firmware_version = "5.0.0"
        client._supports_full_config = True
        await client._setup_api_validator()
        assert client._api_data is not None
        validator = client._validator._api_validator
        first_id = next(iter(client._api_data["device"]))
        validator.validated_parameters["device"] = {first_id}
        original = dict(client._api_data["device"])
        with pytest.raises(BSBLANMalformedResponseError):
            await client._ensure_section_validated("device")
        assert validator.validated_parameters["device"] == {first_id}
        assert client._api_data["device"] == original


@pytest.mark.parametrize(
    ("status", "error"),
    [(401, BSBLANAuthError), (403, BSBLANAuthError), (404, BSBLANConnectionError)],
)
async def test_firmware_5_http_errors_keep_type_and_cause(
    aresponses: ResponsesMockServer, status: int, error: type[Exception]
) -> None:
    """Auth/connection errors are not malformed responses or unavailable days."""
    aresponses.add("example.com", "/JQ", "POST", aresponses.Response(status=status))
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(configured(), session=session)
        client._firmware_version = "5.0.0"
        with pytest.raises(error) as exc:
            await client.heating_schedule(circuit=2)
        assert isinstance(exc.value.__cause__, aiohttp.ClientResponseError)


async def test_programming_error_is_not_reclassified() -> None:
    """Only expected malformed-response errors gain schedule context."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(configured(), session=session)
        client._request = AsyncMock(side_effect=RuntimeError("synthetic bug"))
        with pytest.raises(RuntimeError, match="synthetic bug"):
            await client.hot_water_schedule()


async def test_decode_cause_preserves_original_response_and_location(
    aresponses: ResponsesMockServer,
) -> None:
    """Keep the original decoding document/location through serialization."""
    body = '{\n  "synthetic": "value",\n  invalid\n}'
    with pytest.raises(json.JSONDecodeError) as original:
        json.loads(body)
    aresponses.add("example.com", "/JQ", "POST", aresponses.Response(text=body))
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BSBLANMalformedResponseError) as exc:
            await BSBLAN(configured(), session=session).heating_schedule()
    cause = exc.value.__cause__
    assert isinstance(cause, json.JSONDecodeError)
    restored = pickle.loads(pickle.dumps(cause))  # noqa: S301
    for error in (cause, restored):
        assert (error.doc, error.msg, error.pos, error.lineno, error.colno) == (
            body,
            original.value.msg,
            original.value.pos,
            original.value.lineno,
            original.value.colno,
        )
        assert str(error) == str(original.value)
    assert "heating schedule circuit 1" in str(exc.value)
    assert all(param in str(exc.value) for param in PARAMS.split(","))
    assert body not in str(exc.value)
    assert body not in str(cause)


async def test_non_jq_decode_cause_is_unchanged(
    aresponses: ResponsesMockServer,
) -> None:
    """Other endpoints retain the original JSON decode error document."""
    body = '{"synthetic":"value",'
    aresponses.add("example.com", "/JV", "POST", aresponses.Response(text=body))
    async with aiohttp.ClientSession() as session:
        with pytest.raises(BSBLANMalformedResponseError) as exc:
            await BSBLAN(configured(), session=session)._request(base_path="/JV")
    assert isinstance(exc.value.__cause__, json.JSONDecodeError)
    assert exc.value.__cause__.doc == body
