"""Profile reuse reduces bus traffic without caching observed schedule values."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import (
    BSBLAN,
    BSBLANConnectionError,
    BSBLANMalformedResponseError,
    BSBLANScheduleMappingError,
    BSBLANScheduleProbeError,
    BSBLANScheduleWriteError,
    Device,
    ScheduleMappings,
)
from tests.test_schedule_profile_integration import client, device, update
from tests.test_schedule_profiles import (
    IDS,
    MAPPING,
    controller_data,
    entity,
    probe_data,
    profile,
)


def heating_client() -> BSBLAN:
    """Keep only HC1 certified so explicit refresh probes just one group."""
    return client(
        schedule_profiles=(profile(mappings=ScheduleMappings(heating={1: MAPPING})),)
    )


async def test_first_read_primes_mapping_but_next_read_fetches_fresh_values() -> None:
    """Read again without repeating /JI and the controller identity parameters."""
    subject = heating_client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            {param: entity("09:00-10:00") for param in IDS},
        ]
    )
    first = await subject.heating_schedule()
    second = await subject.heating_schedule()
    assert first.day("monday").raw_value == "06:00-08:00"
    assert second.day("monday").raw_value == "09:00-10:00"
    assert subject._request.await_count == 4
    assert subject._request.await_args_list[-1].kwargs == {
        "params": {"Parameter": ",".join(IDS)}
    }


async def test_explicit_discovery_primes_all_supported_groups() -> None:
    """Repeated successful discovery costs no I/O, but schedule values stay fresh."""
    subject = client(
        schedule_profiles=(
            profile(
                mappings=ScheduleMappings(
                    heating={1: MAPPING, 2: MAPPING},
                    hot_water=MAPPING,
                )
            ),
        )
    )
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            probe_data(),
            probe_data(),
            probe_data(),
        ]
    )
    first = await subject.discover_schedules()
    assert await subject.discover_schedules() == first
    assert subject._request.await_count == 5
    assert (await subject.hot_water_schedule()).complete
    assert subject._request.await_count == 6


async def test_explicit_refresh_replaces_cached_trust() -> None:
    """Consumers choose when to pay for fresh identity and compatibility probes."""
    subject = heating_client()
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
    await subject.heating_schedule()
    assert (await subject.discover_schedules(refresh=True))[0].enabled
    assert subject._request.await_count == 6


async def test_invalidate_is_synchronous_and_has_no_network_side_effect() -> None:
    """HA can clear trust on reconnect without triggering an immediate scan."""
    subject = heating_client()
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
    await subject.heating_schedule()
    assert subject.invalidate_schedule_profiles() is None
    assert subject._request.await_count == 3
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 6


@pytest.mark.parametrize(
    "change", [{"version": "other"}, {"busdest": 99}, {"busaddr": 12}, {"MAC": "other"}]
)
async def test_cached_metadata_change_requires_fresh_resolution(
    change: dict[str, Any],
) -> None:
    """A positive mapping is scoped to the adapter/bus fingerprint it validated."""
    subject = heating_client()
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
    await subject.heating_schedule()
    subject._device = Device(**device(**change))
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 6


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({}, BSBLANScheduleProbeError),
        ({param: entity(dataType=0) for param in IDS}, BSBLANScheduleMappingError),
        ({param: entity(error=7) for param in IDS}, BSBLANScheduleMappingError),
        ([], BSBLANMalformedResponseError),
    ],
)
async def test_failed_cached_read_discards_trust_and_next_attempt_reidentifies(
    response: Any, error: type[Exception]
) -> None:
    """Incomplete data is retryable, never a reason to scan alternative IDs."""
    subject = heating_client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            response,
            device(),
            controller_data(),
            probe_data(),
        ]
    )
    await subject.heating_schedule()
    with pytest.raises(error):
        await subject.heating_schedule()
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 7


async def test_failed_refresh_does_not_restore_old_positive_cache() -> None:
    """A failed explicit refresh cannot leave an obsolete successful proof active."""
    subject = heating_client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            device(),
            controller_data(),
            {},
            device(),
            controller_data(),
            probe_data(),
        ]
    )
    await subject.heating_schedule()
    assert (await subject.discover_schedules(refresh=True))[0].retry_required
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 9


@pytest.mark.parametrize("stage", [0, 1, 2])
async def test_invalidation_during_resolution_prevents_publishing_trust(
    stage: int,
) -> None:
    """A generation change invalidates even a successful in-flight response."""
    subject = heating_client()
    replies = [device(), controller_data(), probe_data()]
    seen = []

    async def request(**kwargs: Any) -> Any:
        index = len(seen)
        seen.append(kwargs)
        if index == stage:
            subject.invalidate_schedule_profiles()
        return replies[index]

    subject._request = request
    with pytest.raises(BSBLANScheduleProbeError, match="discovery_invalidated"):
        await subject.heating_schedule()
    subject._request = AsyncMock(side_effect=replies)
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 3


async def test_invalidation_during_discovery_cannot_prime_any_group() -> None:
    """A multi-group discovery never publishes stale partial trust."""
    subject = heating_client()
    replies = iter([device(), controller_data(), probe_data()])

    async def request(**kwargs: Any) -> Any:
        response = next(replies)
        if kwargs.get("params", {}).get("Parameter") == ",".join(IDS):
            subject.invalidate_schedule_profiles()
        return response

    subject._request = request
    with pytest.raises(BSBLANScheduleProbeError, match="discovery_invalidated"):
        await subject.discover_schedules()
    subject._request = AsyncMock(
        side_effect=[device(), controller_data(), probe_data()]
    )
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 3


async def test_cached_read_rejects_metadata_changed_during_the_request() -> None:
    """Fresh observations cannot be assigned under a changed cached bus target."""
    subject = heating_client()
    subject._request = AsyncMock(
        side_effect=[device(), controller_data(), probe_data()]
    )
    await subject.heating_schedule()

    async def request(**_kwargs: Any) -> Any:
        subject._device = Device(**device(busdest=99))
        return probe_data()

    subject._request = request
    with pytest.raises(BSBLANScheduleMappingError, match="metadata_changed"):
        await subject.heating_schedule()
    subject._request = AsyncMock(
        side_effect=[device(), controller_data(), probe_data()]
    )
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 3


async def test_invalidation_during_cached_read_rejects_the_inflight_result() -> None:
    """Reconfiguration cannot return values under a discarded mapping proof."""
    subject = heating_client()
    subject._request = AsyncMock(
        side_effect=[device(), controller_data(), probe_data()]
    )
    await subject.heating_schedule()

    async def request(**_kwargs: Any) -> Any:
        subject.invalidate_schedule_profiles()
        return probe_data()

    subject._request = request
    with pytest.raises(BSBLANScheduleProbeError, match="discovery_invalidated"):
        await subject.heating_schedule()


async def test_concurrent_first_reads_share_identity_and_compatibility_probe() -> None:
    """Only one successful discovery runs; each reader still receives fresh data."""
    subject = heating_client()
    seen: list[dict[str, Any]] = []

    async def request(**kwargs: Any) -> Any:
        seen.append(kwargs)
        await asyncio.sleep(0)
        if kwargs.get("base_path") == "/JI":
            return device()
        if kwargs["params"]["Parameter"] == "6224,6225,6226":
            return controller_data()
        return probe_data()

    subject._request = request
    results = await asyncio.gather(
        subject.heating_schedule(), subject.heating_schedule()
    )
    assert all(result.complete for result in results)
    assert len(seen) == 4
    assert sum(call.get("base_path") == "/JI" for call in seen) == 1


async def test_cancelled_discovery_releases_lock_without_caching_trust() -> None:
    """Cancellation during a bus probe leaves later attempts free to retry."""
    subject = heating_client()
    started = asyncio.Event()
    waiting = asyncio.Event()

    async def request(**kwargs: Any) -> Any:
        if kwargs.get("base_path") == "/JI":
            return device()
        if kwargs["params"]["Parameter"] == "6224,6225,6226":
            return controller_data()
        started.set()
        await waiting.wait()
        return probe_data()

    subject._request = request
    task = asyncio.create_task(subject.discover_schedules())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    subject._request = AsyncMock(
        side_effect=[device(), controller_data(), probe_data()]
    )
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 3


@pytest.mark.parametrize("failure", [TimeoutError, aiohttp.ClientConnectionError])
async def test_exhausted_transport_failure_invalidates_automatic_trust(
    failure: type[Exception],
) -> None:
    """Even a non-schedule request losing connection discards cached profiles."""
    subject = heating_client()
    subject._transport.request_with_retry = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            failure(),
            device(),
            controller_data(),
            probe_data(),
        ]
    )
    await subject.heating_schedule()
    with pytest.raises(BSBLANConnectionError):
        await subject._request(params={"Parameter": "700"})
    assert (await subject.heating_schedule()).complete
    assert subject._transport.request_with_retry.await_count == 7


async def test_failed_later_group_does_not_cache_partial_discovery() -> None:
    """A connection failure midway through discovery cannot publish partial proof."""
    subject = client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            BSBLANConnectionError(),
            device(),
            controller_data(),
            probe_data(),
        ]
    )
    with pytest.raises(BSBLANConnectionError):
        await subject.discover_schedules()
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 7


async def test_unknown_groups_are_not_negatively_cached() -> None:
    """Unknown circuits may be retried without repeating probes of validated ones."""
    subject = heating_client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            device(),
            controller_data(),
            device(),
            controller_data(),
        ]
    )
    await subject.heating_schedule()
    for _ in range(2):
        availability = await subject.discover_schedules()
        assert availability[0].enabled
        assert availability[1].repair_required
    assert subject._request.await_count == 7


async def test_cached_mapping_never_bypasses_automatic_write_preflight() -> None:
    """Every write must refresh identity and compatibility, even after discovery."""
    subject = heating_client()
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            device(),
            controller_data(),
            probe_data(),
            {IDS[0]: {"status": 1}},
            {IDS[1]: {"status": 1}},
        ]
    )
    await subject.heating_schedule()
    await subject.set_heating_schedule(update())
    assert subject._request.await_count == 8
    assert subject._request.await_args_list[3].kwargs == {"base_path": "/JI"}


async def test_invalidation_between_day_writes_stops_remaining_commands() -> None:
    """Preserve partial acknowledgements when HA invalidates an in-flight update."""
    subject = heating_client()
    seen: list[dict[str, Any]] = []
    replies = [device(), controller_data(), probe_data(), {IDS[0]: {"status": 1}}]

    async def request(**kwargs: Any) -> Any:
        index = len(seen)
        seen.append(kwargs)
        if kwargs.get("base_path") == "/JS":
            subject.invalidate_schedule_profiles()
        return replies[index]

    subject._request = request
    with pytest.raises(BSBLANScheduleWriteError) as err:
        await subject.set_heating_schedule(update())
    assert err.value.acknowledged_days == ("monday",)
    assert err.value.failed_day == "tuesday"
    assert isinstance(err.value.__cause__, BSBLANScheduleProbeError)
    assert len(seen) == 4


@pytest.mark.parametrize("change", ["adapter", "controller"])
async def test_new_identity_cannot_relabel_another_cached_group(change: str) -> None:
    """New metadata observed during resolution must invalidate older group proofs."""
    subject = client()
    changed_identity = controller_data()
    if change == "controller":
        changed_identity["6226"]["value"] = "999"
    subject._request = AsyncMock(
        side_effect=[
            device(),
            controller_data(),
            probe_data(),
            device(version="different-build") if change == "adapter" else device(),
            changed_identity,
        ]
    )
    await subject.heating_schedule()
    with pytest.raises(BSBLANScheduleProbeError, match="discovery_invalidated"):
        await subject.discover_schedules()
    subject._request = AsyncMock(
        side_effect=[device(), controller_data(), probe_data()]
    )
    assert (await subject.heating_schedule()).complete
    assert subject._request.await_count == 3
