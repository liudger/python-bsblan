"""Heating schedule commands use only the configured target and shared values."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig
from bsblan.exceptions import BSBLANInvalidParameterError
from bsblan.schedules import (
    DaySchedule,
    ScheduleMapping,
    ScheduleMappings,
    ScheduleUpdate,
)

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer


@pytest.mark.parametrize("circuit", [True, 1.0, None, 0, 3])
async def test_invalid_write_circuit_is_rejected(circuit) -> None:
    """Invalid circuits fail locally even without any configured mapping."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.invalid"), session=session)
        with pytest.raises(BSBLANInvalidParameterError):
            await client.set_heating_schedule(ScheduleUpdate(), circuit=circuit)


async def test_circuit_profiles_do_not_leak_into_other_circuits(
    aresponses: ResponsesMockServer,
) -> None:
    """Two circuits with different literal profiles never share a weekday ID."""
    one = ScheduleMapping(
        monday="810",
        tuesday="811",
        wednesday="812",
        thursday="813",
        friday="814",
        saturday="815",
        sunday="816",
    )
    two = ScheduleMapping(
        monday="920",
        tuesday="921",
        wednesday="922",
        thursday="923",
        friday="924",
        saturday="925",
        sunday="926",
    )
    seen = []

    async def handler(request: Any) -> Any:
        payload = await request.json()
        seen.append(payload["Parameter"])
        return aresponses.Response(
            text=json.dumps({payload["Parameter"]: {"status": 1}})
        )

    aresponses.add("example.com", "/JS", "POST", handler, repeat=2)
    configured = BSBLANConfig(
        host="example.com",
        schedule_mappings=ScheduleMappings(heating_1=one, heating_2=two),
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(configured, session=session)
        update = ScheduleUpdate(monday=DaySchedule.from_bsblan_format("06:00-08:00"))
        await client.set_heating_schedule(update, circuit=2)
        await client.set_heating_schedule(update, circuit=1)
    assert seen == ["920", "810"]
