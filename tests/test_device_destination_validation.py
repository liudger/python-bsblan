"""Raw JI destinations must not be coerced into a supported profile identity."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from pydantic import ValidationError

from bsblan import (
    BSBLAN,
    BSBLANConfig,
    BSBLANMalformedResponseError,
    DaySchedule,
    Device,
    ScheduleUpdate,
)
from tests.test_standard_schedule_profiles import (
    DHW,
    HC,
    HC_DECIMAL,
    controller,
    device,
    incompatible_structure,
    structure,
    values,
)

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer

CHANGE = ScheduleUpdate(monday=DaySchedule.from_bsblan_format("07:00-09:00"))


@pytest.mark.parametrize("destination", [False, True, 0.0, 1.0, "0"])
@pytest.mark.parametrize("operation", ["discover", "read", "write"])
async def test_public_schedule_api_rejects_malformed_ji_destination(
    aresponses: ResponsesMockServer,
    destination: Any,
    operation: str,
) -> None:
    """Even otherwise compatible layout/value responses cannot certify coerced JI."""
    seen: list[str] = []

    async def handler(request: Any) -> Any:
        seen.append(request.path)
        if request.path == "/JI":
            body = device(busdest=destination)
        elif request.path.startswith("/JC="):
            body = structure(tuple(request.path.split("=", 1)[1].split(",")))
        elif request.path == "/JS":
            body = {HC[0]: {"status": 1}}
        else:
            params = request.query["Parameter"]
            body = (
                controller()
                if params == "6224,6225,6226"
                else values(tuple(params.split(",")))
            )
        return aresponses.Response(text=json.dumps(body))

    for path in ("/JI", "/JQ", "/JC=" + ",".join(HC), "/JC=" + ",".join(DHW), "/JS"):
        aresponses.add("example.com", path, "POST", handler, repeat=5)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        if operation == "discover":
            pending = client.discover_schedules()
        elif operation == "read":
            pending = client.heating_schedule()
        else:
            pending = client.set_heating_schedule(CHANGE)
        with pytest.raises(BSBLANMalformedResponseError):
            await pending
        assert client.device_info is None
    assert seen == ["/JI"]


@pytest.mark.parametrize("destination", [False, 0.0])
async def test_invalid_refresh_cannot_preserve_a_cached_automatic_mapping(
    destination: Any,
) -> None:
    """Do not publish bad metadata or let a prior proof mask a failed refresh."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(),
            controller(),
            structure(),
            incompatible_structure(HC_DECIMAL),
            values(),
            device(busdest=destination),
            device(),
            controller(),
            structure(),
            incompatible_structure(HC_DECIMAL),
            values(),
        ]
    )
    await client.heating_schedule()
    valid_metadata = client.device_info
    assert valid_metadata is not None
    with pytest.raises(BSBLANMalformedResponseError):
        await client.device()
    assert client.device_info is valid_metadata
    assert type(valid_metadata.busdest) is int
    assert (await client.heating_schedule()).complete
    assert client._request.await_count == 11


@pytest.mark.parametrize("present", [False, True])
async def test_absent_destination_is_unknown_not_destination_zero(
    *, present: bool
) -> None:
    """Optional missing/null metadata still permits basic monitoring, not profiles."""
    raw = device(busdest=None)
    if not present:
        raw.pop("busdest")
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(return_value=raw)
    result = await client.discover_schedules()
    assert all(not item.enabled for item in result)
    assert client.device_info is not None
    assert client.device_info.busdest is None
    client._request.assert_awaited_once_with(base_path="/JI")


@pytest.mark.parametrize("destination", [False, 0.0, "0"])
def test_device_model_rejects_non_integer_destination(destination: Any) -> None:
    """The typed identity itself must retain an exact integer rather than coercion."""
    raw = device(busdest=destination)
    with pytest.raises(ValidationError):
        Device.model_validate(raw)
