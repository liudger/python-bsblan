"""Heating schedule commands use only the configured target and shared values."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig
from bsblan.exceptions import BSBLANInvalidParameterError, BSBLANScheduleMappingError
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
        schedule_mappings=ScheduleMappings(heating={1: one, 2: two}),
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(configured, session=session)
        update = ScheduleUpdate(monday=DaySchedule.from_bsblan_format("06:00-08:00"))
        await client.set_heating_schedule(update, circuit=2)
        await client.set_heating_schedule(update, circuit=1)
    assert seen == ["920", "810"]


def keyed_profiles() -> ScheduleMappings:
    """Different literal IDs make cross-circuit routing errors observable."""
    days = (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    )
    return ScheduleMappings(
        heating={
            1: ScheduleMapping(
                **dict(
                    zip(
                        days,
                        ("810", "811", "812", "813", "814", "815", "816"),
                        strict=True,
                    )
                )
            ),
            2: ScheduleMapping(
                **dict(
                    zip(
                        days,
                        ("920", "921", "922", "923", "924", "925", "926"),
                        strict=True,
                    )
                )
            ),
        }
    )


async def test_keyed_profile_is_shared_by_circuit_reads_and_writes(
    aresponses: ResponsesMockServer,
) -> None:
    """The single circuit identifier selects identical profiles in both directions."""
    seen = []

    async def handler(request: Any) -> Any:
        if request.path == "/JQ":
            params = request.query["Parameter"]
            seen.append((request.path, params))
            body = {
                params.split(",")[0]: {
                    "name": "x",
                    "value": "06:00-08:00",
                    "unit": "",
                    "desc": "",
                    "dataType": 9,
                    "error": 0,
                }
            }
        else:
            payload = await request.json()
            seen.append((request.path, payload["Parameter"]))
            body = {payload["Parameter"]: {"status": 1}}
        return aresponses.Response(text=json.dumps(body))

    for path in ("/JQ", "/JS"):
        aresponses.add("example.com", path, "POST", handler, repeat=2)
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(
            BSBLANConfig(host="example.com", schedule_mappings=keyed_profiles()),
            session=session,
        )
        for circuit in (2, 1):
            observed = await client.heating_schedule(circuit=circuit)
            assert observed.circuit == circuit
            await client.set_heating_schedule(
                ScheduleUpdate(monday=observed.day("monday").schedule), circuit=circuit
            )
    assert seen == [
        ("/JQ", "920,921,922,923,924,925,926"),
        ("/JS", "920"),
        ("/JQ", "810,811,812,813,814,815,816"),
        ("/JS", "810"),
    ]


@pytest.mark.parametrize("operation", ["read", "write"])
async def test_missing_circuit_never_falls_back_to_another_profile(
    operation: str,
) -> None:
    """A configured circuit 1 is not a default profile for circuit 2."""
    profiles = ScheduleMappings(heating={1: keyed_profiles().heating[1]})
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(
            BSBLANConfig(host="example.com", schedule_mappings=profiles),
            session=session,
        )
        client._request = AsyncMock()
        request = (
            client.heating_schedule(circuit=2)
            if operation == "read"
            else client.set_heating_schedule(
                ScheduleUpdate(monday=DaySchedule.from_bsblan_format("06:00-08:00")),
                circuit=2,
            )
        )
        with pytest.raises(BSBLANScheduleMappingError, match="mapping_unknown") as exc:
            await request
        assert exc.value.circuit == 2
        client._request.assert_not_awaited()
