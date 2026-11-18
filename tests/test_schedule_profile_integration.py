"""Exercise automatic profile resolution through the public schedule API."""

from __future__ import annotations

import json
from datetime import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import (
    BSBLAN,
    BSBLANConfig,
    BSBLANConnectionError,
    BSBLANScheduleMappingError,
    BSBLANScheduleProbeError,
    BSBLANScheduleWriteError,
    BSBLANUnsupportedFeatureError,
    DaySchedule,
    Device,
    ScheduleMappings,
    ScheduleProfile,
    ScheduleProfileIdentity,
    ScheduleUpdate,
    TimeSlot,
)
from bsblan.exceptions import BSBLANAuthError, BSBLANMalformedResponseError
from tests.test_schedule_profiles import (
    IDENTITY,
    IDS,
    MAPPING,
    controller_data,
    entity,
    probe_data,
    profile,
)

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer


def client(**changes: Any) -> BSBLAN:
    """Use explicit synthetic profiles, not defaults claiming real evidence."""
    return BSBLAN(
        BSBLANConfig(
            **{
                "host": "example.com",
                "schedule_profiles": (profile(),),
                "schedule_table": "synthetic-test-table",
                **changes,
            }
        )
    )


def device(**changes: Any) -> dict[str, Any]:
    """Build /JI raw JSON for the synthetic installation."""
    return {
        "name": "Test",
        "version": "test-build",
        "MAC": "test",
        "uptime": 0,
        "bus": "BSB",
        "busdest": 0,
        **changes,
    }


def update() -> ScheduleUpdate:
    """Change two weekdays with the ordinary shared schedule model."""
    day = DaySchedule((TimeSlot(time(6), time(8)),))
    return ScheduleUpdate(monday=day, tuesday=day)


async def test_public_profile_types_and_config_capture() -> None:
    """Expose immutable declarations through the supported package API."""
    assert isinstance(profile(), ScheduleProfile)
    assert profile().identity == ScheduleProfileIdentity(**IDENTITY)
    subject = client()
    subject.config.schedule_profiles = ()
    subject.config.schedule_table = "changed-after-construction"
    subject._request = AsyncMock(
        side_effect=[device(), controller_data(), probe_data()]
    )
    assert (await subject.heating_schedule()).complete


async def test_public_discovery_has_independent_group_statuses() -> None:
    """One unsupported circuit does not hide compatible heating and DHW."""
    subject = client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            probe_data(),
        ]
    )
    availability = await subject.discover_schedules()
    assert [(item.kind, item.circuit, item.status) for item in availability] == [
        ("heating", 1, "enabled"),
        ("heating", 2, "unknown"),
        ("hot_water", None, "enabled"),
    ]
    assert all(
        call.kwargs.get("base_path") != "/JS"
        for call in subject._request.await_args_list
    )
    assert subject._request.await_count == 4


async def test_manual_mappings_override_automatic_group_without_probe() -> None:
    """Manual configuration remains a local assertion, preserving legacy I/O."""
    subject = client(schedule_mappings=ScheduleMappings(heating={1: MAPPING}))
    subject._request = AsyncMock(return_value=probe_data())
    snapshot = await subject.heating_schedule()
    assert snapshot.complete
    subject._request.assert_awaited_once_with(params={"Parameter": ",".join(IDS)})


async def test_all_manual_discovery_never_fetches_metadata_or_parameters() -> None:
    """Even discovery does not unexpectedly verify caller-confirmed overrides."""
    subject = client(
        schedule_mappings=ScheduleMappings(
            heating={1: MAPPING, 2: MAPPING}, hot_water=MAPPING
        )
    )
    subject._request = AsyncMock()
    availability = await subject.discover_schedules()
    assert all(item.enabled and item.source == "manual" for item in availability)
    subject._request.assert_not_awaited()


async def test_automatic_read_reuses_mapping_and_rechecks_fresh_values() -> None:
    """No stale values or repeated identity traffic after a successful probe."""
    subject = client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            {param: entity("06:00-24:00") for param in IDS},
        ]
    )
    assert (await subject.heating_schedule()).complete
    later = await subject.heating_schedule()
    assert later.day("monday").status == "unparsed"
    assert subject._request.await_count == 4


@pytest.mark.parametrize("kind", ["heating", "hot_water"])
async def test_automatic_write_probes_before_sequential_js(kind: str) -> None:
    """Exactly the profile's IDs drive both automatic readers and setters."""
    subject = client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            {IDS[0]: {"status": 1}},
            {IDS[1]: {"status": 1}},
        ]
    )
    if kind == "heating":
        await subject.set_heating_schedule(update())
    else:
        await subject.set_hot_water_schedule(update())
    calls = subject._request.await_args_list
    assert [call.kwargs.get("base_path", "/JQ") for call in calls] == [
        "/JI",
        "/JQ",
        "/JQ",
        "/JS",
        "/JS",
    ]
    assert [call.kwargs["data"]["Parameter"] for call in calls[-2:]] == list(IDS[:2])


async def test_incomplete_probe_has_distinct_retry_error_then_recovers() -> None:
    """HA must not turn a transient discovery failure into a wrong-mapping repair."""
    subject = client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            {},
            device(),
            controller_data(),
            probe_data(),
        ]
    )
    with pytest.raises(BSBLANScheduleProbeError) as err:
        await subject.heating_schedule()
    assert not isinstance(err.value, BSBLANScheduleMappingError)
    assert err.value.reason == "probe_incomplete"
    assert (await subject.heating_schedule()).complete


async def test_incompatible_probe_blocks_writes_with_mapping_reason() -> None:
    """Wrong TIMEPROG types cannot be bypassed by calling the setter first."""
    subject = client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            {param: entity(dataType=0) for param in IDS},
        ]
    )
    change = update()
    with pytest.raises(BSBLANScheduleMappingError, match="probe_incompatible"):
        await subject.set_heating_schedule(change)
    assert subject._request.await_count == 3


async def test_connection_errors_propagate_from_discovery_and_recover() -> None:
    """The library does not permanently cache a temporary offline installation."""
    subject = client()
    subject._request = AsyncMock(
        side_effect=[
            BSBLANConnectionError(),
            device(),
            controller_data(),
            probe_data(),
            probe_data(),
        ]
    )
    with pytest.raises(BSBLANConnectionError):
        await subject.discover_schedules()
    assert (await subject.discover_schedules())[0].enabled


@pytest.mark.parametrize("stage", [0, 1, 2, 3])
async def test_target_change_during_resolution_or_write_never_redirects_next_write(
    stage: int,
) -> None:
    """Check transport identity after each await and between weekday writes."""
    subject = client()
    replies = [device(), controller_data(), probe_data(), {IDS[0]: {"status": 1}}]
    seen: list[dict[str, Any]] = []

    async def request(**kwargs: Any) -> Any:
        index = len(seen)
        seen.append(kwargs)
        if index == stage:
            subject.config.host = "other.example"
        return replies[index]

    subject._request = request
    expected = BSBLANScheduleWriteError if stage == 3 else BSBLANScheduleMappingError
    change = update()
    with pytest.raises(expected):
        await subject.set_heating_schedule(change)
    assert len(seen) == stage + 1


@pytest.mark.parametrize("stage", [1, 2, 3])
async def test_cached_metadata_change_during_probe_or_write_is_guarded(
    stage: int,
) -> None:
    """Changes to bus destination or firmware invalidate the in-flight proof."""
    subject = client()
    replies = [device(), controller_data(), probe_data(), {IDS[0]: {"status": 1}}]
    seen: list[dict[str, Any]] = []

    async def request(**kwargs: Any) -> Any:
        index = len(seen)
        seen.append(kwargs)
        if index == stage:
            subject._device = Device(**device(busdest=99))
        return replies[index]

    subject._request = request
    expected = BSBLANScheduleWriteError if stage == 3 else BSBLANScheduleMappingError
    change = update()
    with pytest.raises(expected):
        await subject.set_heating_schedule(change)
    assert len(seen) == stage + 1


async def test_known_pps_rejected_without_automatic_network_requests() -> None:
    """Preserve existing PPS schedule rejection even with a profile registry."""
    subject = client()
    subject._device = Device(**device(bus="PPS"))
    subject._request = AsyncMock()
    with pytest.raises(BSBLANUnsupportedFeatureError):
        await subject.heating_schedule()
    subject._request.assert_not_awaited()


@pytest.mark.parametrize("cached", [True, False])
async def test_discovery_pps_disables_even_manual_overrides(*, cached: bool) -> None:
    """Fresh PPS metadata cannot leave an earlier manual group advertised enabled."""
    subject = client(schedule_mappings=ScheduleMappings(heating={1: MAPPING}))
    if cached:
        subject._device = Device(**device(bus="PPS"))
    subject._request = AsyncMock(return_value=device(bus="PPS"))
    availability = await subject.discover_schedules()
    assert all(
        not item.enabled and item.reason == "pps_unsupported" for item in availability
    )
    assert subject._request.await_count == (0 if cached else 1)


async def test_discovery_keeps_independent_manual_and_retry_outcomes() -> None:
    """Keep useful discovery outcomes without all-or-nothing enablement."""
    subject = client(schedule_mappings=ScheduleMappings(heating={1: MAPPING}))
    subject._request = AsyncMock(side_effect=[device(), controller_data(), {}])
    availability = await subject.discover_schedules()
    assert availability[0].enabled
    assert availability[0].source == "manual"
    assert availability[1].repair_required
    assert availability[2].retry_required
    assert not availability[2].repair_required


async def test_profiles_do_not_add_eager_initialization_requests() -> None:
    """Normal initialization stays lazy even when automatic profiles are configured."""
    subject = client()
    subject._request = AsyncMock(side_effect=[device(), {"api_version": "3.0"}])
    await subject.initialize()
    assert [call.kwargs for call in subject._request.await_args_list] == [
        {"base_path": "/JI"},
        {"base_path": "/JV"},
    ]


async def test_automatic_hc2_and_dhw_reads_use_exact_profile_ids() -> None:
    """The same resolver supports the second heating circuit and hot-water reader."""
    subject = client(
        schedule_profiles=(
            profile(mappings=ScheduleMappings(heating={2: MAPPING}, hot_water=MAPPING)),
        )
    )
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            device(),
            controller_data(),
            probe_data(),
        ]
    )
    assert (await subject.heating_schedule(circuit=2)).circuit == 2
    assert (await subject.hot_water_schedule()).kind == "hot_water"


@pytest.mark.parametrize("kind", ["heating", "hot_water"])
async def test_automatic_schedule_real_http_boundary(
    aresponses: ResponsesMockServer, kind: str
) -> None:
    """Prove profile resolution uses only /JI and the exact read-only /JQ IDs."""
    seen: list[tuple[str, str | None]] = []

    async def handler(request: Any) -> Any:
        params = request.query.get("Parameter")
        seen.append((request.path, params))
        response = {
            None: device(),
            "6224,6225,6226": controller_data(),
            ",".join(IDS): probe_data(),
        }[params]
        return aresponses.Response(text=json.dumps(response))

    aresponses.add("example.com", "/JI", "POST", handler)
    aresponses.add("example.com", "/JQ", "POST", handler, repeat=2)
    async with aiohttp.ClientSession() as session:
        subject = client()
        subject.session = session
        snapshot = (
            await subject.heating_schedule()
            if kind == "heating"
            else await subject.hot_water_schedule()
        )
    assert snapshot.complete
    assert [day.parameter_id for day in snapshot.days] == list(IDS)
    assert seen == [
        ("/JI", None),
        ("/JQ", "6224,6225,6226"),
        ("/JQ", ",".join(IDS)),
    ]


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [(401, "", BSBLANAuthError), (200, "not-json", BSBLANMalformedResponseError)],
)
async def test_automatic_http_failures_keep_classification(
    aresponses: ResponsesMockServer, status: int, body: str, error: type[Exception]
) -> None:
    """Authentication and malformed data cannot become profile mismatch repairs."""
    aresponses.add(
        "example.com",
        "/JI",
        "POST",
        aresponses.Response(text=json.dumps(device())),
    )
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(status=status, text=body),
    )
    async with aiohttp.ClientSession() as session:
        subject = client()
        subject.session = session
        with pytest.raises(error):
            await subject.discover_schedules()


async def test_explicit_empty_registry_never_does_schedule_io() -> None:
    """Disabling automatic profiles retains the opt-out's local no-I/O failure."""
    subject = BSBLAN(BSBLANConfig(host="example.com", schedule_profiles=()))
    subject._request = AsyncMock()
    assert all(item.repair_required for item in await subject.discover_schedules())
    with pytest.raises(BSBLANScheduleMappingError):
        await subject.hot_water_schedule()
    subject._request.assert_not_awaited()
