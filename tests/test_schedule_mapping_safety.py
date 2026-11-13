"""Literal integer/decimal profiles are caller assertions, not discovery rules."""

from __future__ import annotations

import json
from datetime import time
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig
from bsblan.schedules import ScheduleMapping, ScheduleMappings

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
PROFILES = [
    ("heating_1", ("501", "501.1", "501.2", "501.3", "501.4", "501.5", "501.6")),
    ("heating_2", ("521", "521.1", "521.2", "521.3", "521.4", "521.5", "521.6")),
    ("hot_water", ("561", "561.1", "561.2", "561.3", "561.4", "561.5", "561.6")),
    ("heating_1", ("502", "502.1", "502.2", "502.3", "502.4", "502.5", "502.6")),
    ("heating_2", ("522", "522.1", "522.2", "522.3", "522.4", "522.5", "522.6")),
    ("hot_water", ("564", "564.1", "564.2", "564.3", "564.4", "564.5", "564.6")),
]


@pytest.mark.parametrize(("group", "ids"), PROFILES)
async def test_literal_profiles_preserve_day_roles(
    aresponses: ResponsesMockServer, group: str, ids: tuple[str, ...]
) -> None:
    """Reordering responses never assigns Monday's value to another day."""
    profile = ScheduleMapping(**dict(zip(DAYS, ids, strict=True)))
    response = {
        param: {
            "name": "x",
            "value": f"{i + 6:02}:00-{i + 7:02}:00",
            "unit": "",
            "desc": "",
            "error": 0,
            "dataType": 9,
        }
        for i, param in enumerate(ids)
    }
    seen = []

    async def handler(request: Any) -> Any:
        seen.append(request.query["Parameter"])
        return aresponses.Response(
            text=json.dumps(dict(reversed(list(response.items()))))
        )

    aresponses.add("example.com", "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(
            BSBLANConfig(
                host="example.com",
                schedule_mappings=ScheduleMappings(**{group: profile}),
            ),
            session=session,
        )
        result = (
            await client.hot_water_schedule()
            if group == "hot_water"
            else await client.heating_schedule(circuit=2 if group == "heating_2" else 1)
        )
    assert result.complete
    assert seen == [",".join(ids)]
    for i, day in enumerate(result.days):
        assert day.weekday == DAYS[i]
        assert day.parameter_id == ids[i]
        assert day.schedule.slots[0].start == time(i + 6)


async def test_same_firmware_devices_do_not_share_profiles(
    aresponses: ResponsesMockServer,
) -> None:
    """Firmware version equality cannot establish the active controller table."""
    seen = []

    async def handler(request: Any) -> Any:
        seen.append(request.query["Parameter"])
        return aresponses.Response(text="{}")

    aresponses.add("example.com", "/JQ", "POST", handler, repeat=2)
    async with aiohttp.ClientSession() as session:
        for _, ids in (PROFILES[0], PROFILES[3]):
            profile = ScheduleMapping(**dict(zip(DAYS, ids, strict=True)))
            client = BSBLAN(
                BSBLANConfig(
                    host="example.com",
                    schedule_mappings=ScheduleMappings(heating_1=profile),
                ),
                session=session,
            )
            client._firmware_version = "5.0.0"
            await client.heating_schedule()
    assert seen == [
        "501,501.1,501.2,501.3,501.4,501.5,501.6",
        "502,502.1,502.2,502.3,502.4,502.5,502.6",
    ]
