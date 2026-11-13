"""DHW uses the same partial update contract and conservative write validation."""

from __future__ import annotations

import json
from datetime import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig
from bsblan.exceptions import BSBLANInvalidParameterError, BSBLANUnsupportedFeatureError
from bsblan.schedules import (
    DaySchedule,
    ScheduleMapping,
    ScheduleMappings,
    ScheduleUpdate,
)

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer


async def test_all_hot_water_days_are_separate_acknowledged_requests(
    aresponses: ResponsesMockServer,
) -> None:
    """The library never collapses a week into one /JS request or a factory reset."""
    profile = ScheduleMapping(
        monday="810",
        tuesday="811",
        wednesday="812",
        thursday="813",
        friday="814",
        saturday="815",
        sunday="816",
    )
    seen = []

    async def handler(request: Any) -> Any:
        payload = await request.json()
        seen.append(payload)
        return aresponses.Response(
            text=json.dumps({payload["Parameter"]: {"status": 1}})
        )

    aresponses.add("example.com", "/JS", "POST", handler, repeat=7)
    configured = BSBLANConfig(
        host="example.com", schedule_mappings=ScheduleMappings(hot_water=profile)
    )
    day = DaySchedule.from_bsblan_format("06:00-08:00")
    async with aiohttp.ClientSession() as session:
        await BSBLAN(configured, session=session).set_hot_water_schedule(
            ScheduleUpdate(
                monday=day,
                tuesday=day,
                wednesday=day,
                thursday=day,
                friday=day,
                saturday=day,
                sunday=day,
            )
        )
    assert [payload["Parameter"] for payload in seen] == [
        "810",
        "811",
        "812",
        "813",
        "814",
        "815",
        "816",
    ]
    assert all(
        payload["Value"] == "06:00-08:00" and payload["Type"] == "1" for payload in seen
    )


@pytest.mark.parametrize("clear", [False, True])
async def test_corrupted_or_clear_dhw_update_cannot_partially_write(
    clear: bool,  # noqa: FBT001
) -> None:
    """Even a bypassed frozen value is fully validated before earlier days write."""
    profile = ScheduleMapping(
        monday="810",
        tuesday="811",
        wednesday="812",
        thursday="813",
        friday="814",
        saturday="815",
        sunday="816",
    )
    day = DaySchedule.from_bsblan_format("06:00-08:00")
    update = ScheduleUpdate(monday=day, sunday=DaySchedule() if clear else day)
    if not clear:
        object.__setattr__(update.sunday.slots[0], "end", time(5))
    async with aiohttp.ClientSession() as session:
        configured = BSBLANConfig(
            host="example.com", schedule_mappings=ScheduleMappings(hot_water=profile)
        )
        client = BSBLAN(configured, session=session)
        client._request = AsyncMock()
        with pytest.raises(
            (BSBLANInvalidParameterError, BSBLANUnsupportedFeatureError)
        ):
            await client.set_hot_water_schedule(update)
        client._request.assert_not_awaited()
