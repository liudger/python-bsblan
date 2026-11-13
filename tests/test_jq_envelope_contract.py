"""Synthetic /JQ object boundary and legacy-client recovery regressions."""

from __future__ import annotations

import json
import pickle
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

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


@pytest.mark.parametrize("firmware", [None, "4.9.9", "5.0.0"])
@pytest.mark.parametrize(
    "body", ['["payload"]', "[]", "null", "17", "false", '"secret-response"']
)
@pytest.mark.parametrize("route", ["parameters", "heating", "hot_water", "device"])
async def test_legacy_rejects_malformed_then_recovers(
    aresponses: ResponsesMockServer, firmware: str | None, body: str, route: str
) -> None:
    """Do not cache a malformed envelope; a later valid request must run."""
    calls: list[tuple[str, str, str | None]] = []

    async def handler(request: Any) -> Any:
        params = request.query.get("Parameter")
        calls.append((request.method, request.path, params))
        if len(calls) == 1:
            return aresponses.Response(text=body)
        entities = {
            param: {
                "name": "synthetic",
                "value": "0" if param == "576" else "06:00-07:00",
                "unit": "",
                "desc": "",
                "error": 0,
                "dataType": 1 if param == "576" else 9,
            }
            for param in params.split(",")
        }
        return aresponses.Response(text=json.dumps(entities))

    for _ in range(3):
        aresponses.add("example.com", "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._firmware_version = firmware
        client._supports_full_config = True
        await client._setup_api_validator()
        assert client._api_data is not None
        original = dict(client._api_data["device"])
        validator = client._validator
        assert validator._api_validator is not None

        async def read() -> Any:
            if route == "parameters":
                return await client.read_parameters(["501"])
            if route == "heating":
                return await client.heating_schedule(include=["monday"])
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
        assert len(calls) == (3 if route == "hot_water" else 2)
        assert all(method == "POST" and path == "/JQ" for method, path, _ in calls)
        assert calls[0][2] == calls[1][2]
        if route == "parameters":
            assert result["501"].value == "06:00-07:00"
        elif route == "heating":
            assert result.monday.value == "06:00-07:00"
        elif route == "hot_water":
            assert result.dhw_time_program_monday.value == "06:00-07:00"
            assert "schedule" in validator._validated_hot_water_groups
        else:
            assert client._api_data["device"] == original
            assert validator._api_validator.is_section_validated("device")


@pytest.mark.parametrize("firmware", [None, "4.9.9", "5.0.0"])
async def test_empty_object_is_valid_but_not_an_empty_week(
    aresponses: ResponsesMockServer, firmware: str | None
) -> None:
    """An empty object denotes missing days, never seven empty schedules."""
    aresponses.add("example.com", "/JQ", "POST", aresponses.Response(text="{}"))
    mapping = ScheduleReadMapping(
        monday="501",
        tuesday="502",
        wednesday="503",
        thursday="504",
        friday="505",
        saturday="506",
        sunday="507",
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._firmware_version = firmware
        snapshot = await client.get_heating_schedule(mapping=mapping)
    assert not snapshot.complete
    assert all(
        day.status == "unavailable" and day.schedule is None
        for day in snapshot.days.values()
    )


@pytest.mark.parametrize("path", ["/JS", "/JV", "/JI"])
async def test_non_jq_non_object_is_unchanged(
    aresponses: ResponsesMockServer, path: str
) -> None:
    """Do not impose /JQ's object contract on other endpoints."""
    aresponses.add("example.com", path, "POST", aresponses.Response(text='["payload"]'))
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._firmware_version = "5.0.0"
        assert await client._request(base_path=path) == ["payload"]


@pytest.mark.parametrize("group", [("heating", 1), ("heating", 2), ("hot_water", None)])
async def test_decode_error_has_context_and_original_cause(
    aresponses: ResponsesMockServer, group: tuple[str, int | None]
) -> None:
    """Real JSON decode errors keep their details, cause, and schedule context."""
    calls: list[str] = []

    async def handler(request: Any) -> Any:
        calls.append(request.query["Parameter"])
        return aresponses.Response(text="{bad")

    aresponses.add("example.com", "/JQ", "POST", handler)
    mapping = ScheduleReadMapping(
        monday="501",
        tuesday="502",
        wednesday="503",
        thursday="504",
        friday="505",
        saturday="506",
        sunday="507",
    )
    kind, circuit = group
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._firmware_version = "5.0.0"
        if kind == "heating":
            assert circuit is not None
            request = client.get_heating_schedule(circuit=circuit, mapping=mapping)
        else:
            request = client.get_hot_water_schedule(mapping=mapping)
        with pytest.raises(BSBLANMalformedResponseError) as exc:
            await request
        assert isinstance(exc.value.__cause__, json.JSONDecodeError)
        assert "line 1" in str(exc.value)
        assert f"{kind} schedule circuit {circuit}" in str(exc.value)
        assert all(param in str(exc.value) for param in mapping.model_dump().values())
    assert calls == [",".join(mapping.model_dump().values())]


async def test_existing_partial_device_validation_survives_malformed(
    aresponses: ResponsesMockServer,
) -> None:
    """A failed subsequent validation must not clear earlier validated IDs."""
    aresponses.add("example.com", "/JQ", "POST", aresponses.Response(text="[]"))
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._firmware_version = "5.0.0"
        client._supports_full_config = True
        await client._setup_api_validator()
        assert client._api_data is not None
        api_validator = client._validator._api_validator
        assert api_validator is not None
        first_id = next(iter(client._api_data["device"]))
        api_validator.validated_parameters["device"] = {first_id}
        original = dict(client._api_data["device"])
        with pytest.raises(BSBLANMalformedResponseError):
            await client._ensure_section_validated("device")
        assert api_validator.validated_parameters["device"] == {first_id}
        assert client._api_data["device"] == original


@pytest.mark.parametrize(
    ("status", "error"),
    [(401, BSBLANAuthError), (403, BSBLANAuthError), (404, BSBLANConnectionError)],
)
async def test_firmware_5_http_errors_keep_type_and_cause(
    aresponses: ResponsesMockServer, status: int, error: type[Exception]
) -> None:
    """Authentication and connection failures are never classified as malformed."""
    calls: list[str] = []

    async def handler(request: Any) -> Any:
        calls.append(request.path)
        return aresponses.Response(status=status)

    aresponses.add("example.com", "/JQ", "POST", handler)
    mapping = ScheduleReadMapping(
        monday="501",
        tuesday="502",
        wednesday="503",
        thursday="504",
        friday="505",
        saturday="506",
        sunday="507",
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._firmware_version = "5.0.0"
        with pytest.raises(error) as exc:
            await client.get_heating_schedule(circuit=2, mapping=mapping)
        assert isinstance(exc.value.__cause__, aiohttp.ClientResponseError)
    assert calls == ["/JQ"]


async def test_programming_error_is_not_reclassified() -> None:
    """The structured reader catches malformed-response errors only."""
    mapping = ScheduleReadMapping(
        monday="501",
        tuesday="502",
        wednesday="503",
        thursday="504",
        friday="505",
        saturday="506",
        sunday="507",
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._request = AsyncMock(side_effect=RuntimeError("synthetic bug"))
        with pytest.raises(RuntimeError, match="synthetic bug"):
            await client.get_hot_water_schedule(mapping=mapping)


async def test_decode_cause_preserves_original_response_and_location(
    aresponses: ResponsesMockServer,
) -> None:
    """Keep the original decode error and its location through serialization."""
    body = '{\n  "synthetic": "value",\n  invalid\n}'
    with pytest.raises(json.JSONDecodeError) as original:
        json.loads(body)
    aresponses.add("example.com", "/JQ", "POST", aresponses.Response(text=body))
    mapping = ScheduleReadMapping(
        monday="501",
        tuesday="502",
        wednesday="503",
        thursday="504",
        friday="505",
        saturday="506",
        sunday="507",
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        with pytest.raises(BSBLANMalformedResponseError) as exc:
            await client.get_heating_schedule(mapping=mapping)
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
    assert all(param in str(exc.value) for param in mapping.model_dump().values())
    assert body not in str(exc.value)
    assert body not in str(cause)


async def test_non_jq_decode_cause_is_unchanged(
    aresponses: ResponsesMockServer,
) -> None:
    """Other endpoints retain the original JSON decode error document."""
    body = '{"synthetic":"value",'
    aresponses.add("example.com", "/JV", "POST", aresponses.Response(text=body))
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        with pytest.raises(BSBLANMalformedResponseError) as exc:
            await client._request(base_path="/JV")
    assert isinstance(exc.value.__cause__, json.JSONDecodeError)
    assert exc.value.__cause__.doc == body
