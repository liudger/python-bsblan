"""Regressions for PR #1678's permission, retry and local-validation findings."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import aiohttp
import pytest

from bsblan import (
    BSBLAN,
    BSBLANConfig,
    BSBLANConnectionError,
    BSBLANError,
    BSBLANInvalidParameterError,
    BSBLANScheduleMappingError,
    BSBLANScheduleProbeError,
    BSBLANScheduleWriteError,
    BSBLANUnsupportedFeatureError,
    DaySchedule,
    Device,
    ScheduleUpdate,
)
from tests.test_standard_schedule_profiles import (
    HC,
    controller,
    device,
    structure,
    values,
)
from tests.test_unified_schedules import config as manual_config

DAY = DaySchedule.from_bsblan_format("07:00-09:00")
CHANGE = ScheduleUpdate(monday=DAY)


def value_response(permission: int | None) -> dict[str, Any]:
    """Keep the value probe compatible even when it does not carry permissions."""
    result = values()
    if permission is None:
        result[HC[0]].pop("readwrite")
    else:
        result[HC[0]]["readwrite"] = permission
    return result


@pytest.mark.parametrize("denial", [1, 2])
@pytest.mark.parametrize("value_permission", [None, 0])
async def test_layout_denial_wins_over_absent_or_allowing_value_permissions(
    denial: int,
    value_permission: int | None,
) -> None:
    """A fresh JC denial must survive a permission-less or contradictory JQ result."""
    layout = structure()
    layout[HC[0]]["readwrite"] = denial
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(buswritable=1),
            controller(),
            layout,
            value_response(value_permission),
            {HC[0]: {"status": 1}},
        ]
    )
    with pytest.raises(BSBLANUnsupportedFeatureError):
        await client.set_heating_schedule(CHANGE)
    assert client._request.await_count == 4
    assert all(
        c.kwargs.get("base_path") != "/JS" for c in client._request.await_args_list
    )


async def test_fresh_layout_allowance_avoids_redundant_permission_request() -> None:
    """Use current JC readwrite=0 when JQ omits flags under disabled defaults."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(buswritable=0),
            controller(),
            structure(),
            value_response(None),
            {HC[0]: {"status": 1}},
        ]
    )
    await client.set_heating_schedule(CHANGE)
    assert client._request.await_count == 5
    assert client._request.await_args_list[-1].kwargs["base_path"] == "/JS"


async def test_cached_discovery_does_not_cache_layout_write_permissions() -> None:
    """A later write must honor a newly observed denial, not a prior read's allow."""
    denied = structure()
    denied[HC[0]]["readwrite"] = 1
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(buswritable=1),
            controller(),
            structure(),
            values(),
            device(buswritable=1),
            controller(),
            denied,
            value_response(None),
            {HC[0]: {"status": 1}},
        ]
    )
    await client.heating_schedule()
    with pytest.raises(BSBLANUnsupportedFeatureError):
        await client.set_heating_schedule(CHANGE)
    assert client._request.await_count == 8


@pytest.mark.parametrize(
    ("bad_update", "error"),
    [
        (None, BSBLANInvalidParameterError),
        ("raw", BSBLANInvalidParameterError),
        (ScheduleUpdate(), BSBLANInvalidParameterError),
        (ScheduleUpdate(monday=DaySchedule()), BSBLANUnsupportedFeatureError),
    ],
)
@pytest.mark.parametrize("automatic", [True, False])
async def test_invalid_update_is_rejected_before_resolution_io(
    bad_update: Any,
    error: type[Exception],
    *,
    automatic: bool,
) -> None:
    """Local input failures must not depend on device connectivity or mappings."""
    config = BSBLANConfig(host="example.com")
    if not automatic:
        config.schedule_profiles = ()
    client = BSBLAN(config)
    client._request = AsyncMock(side_effect=BSBLANConnectionError("must not request"))
    with pytest.raises(error):
        await client.set_heating_schedule(bad_update)
    client._request.assert_not_awaited()


def reply(body: dict[str, Any]) -> Any:
    """Build a fake HTTP context; transport retries still execute for real."""
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.read = AsyncMock(return_value=json.dumps(body).encode())
    context = MagicMock()
    context.__aenter__.return_value = response
    return context


@pytest.mark.parametrize("field", ["host", "port", "passkey"])
async def test_single_day_retry_cannot_follow_a_changed_transport_target(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    """Even a successful second response cannot authorize a retargeted retry."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(manual_config(), session=session)
        client._device = Device(**device(buswritable=1))
        request = Mock(
            side_effect=[
                aiohttp.ClientConnectionError("transient"),
                reply({"700": {"status": 1}}),
            ]
        )
        session.request = request

        async def backoff(_delay: float) -> None:
            setattr(
                client.config,
                field,
                {"host": "other.example", "port": 8081, "passkey": "changed"}[field],
            )

        monkeypatch.setattr("backoff._async.asyncio.sleep", backoff)
        with pytest.raises(BSBLANScheduleWriteError) as err:
            await client.set_heating_schedule(CHANGE)
        assert request.call_count == 1
        assert isinstance(err.value.__cause__, BSBLANScheduleMappingError)
        assert err.value.acknowledged_days == ()
        assert err.value.failed_day == "monday"
        # A failed guarded write must not constrain an unrelated later read.
        await client._request(params={"Parameter": "700"})
        assert request.call_count == 2


@pytest.mark.parametrize(
    "change", ["metadata", "generation", "permission", "unchanged"]
)
async def test_automatic_retry_rechecks_current_mapping_and_permission_proof(
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    """Retry backoff cannot keep using revoked automatic preflight evidence."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        writes = []

        def dispatch(_method: str, url: Any, **kwargs: Any) -> Any:
            if url.path == "/JI":
                return reply(device(buswritable=1))
            if url.path.startswith("/JC="):
                return reply(structure())
            if url.path == "/JQ":
                return reply(
                    controller()
                    if kwargs["params"]["Parameter"] == "6224,6225,6226"
                    else values()
                )
            writes.append(str(url))
            if len(writes) == 1:
                message = "transient"
                raise aiohttp.ClientConnectionError(message)
            return reply({HC[0]: {"status": 1}})

        session.request = Mock(side_effect=dispatch)

        async def backoff(_delay: float) -> None:
            if change == "metadata":
                client._device.busdest = 99
            elif change == "generation":
                client.invalidate_schedule_profiles()
            elif change == "permission":
                client._device.buswritable = 0

        monkeypatch.setattr("backoff._async.asyncio.sleep", backoff)
        if change == "unchanged":
            await client.set_heating_schedule(CHANGE)
            assert len(writes) == 2
            return
        with pytest.raises(BSBLANScheduleWriteError) as err:
            await client.set_heating_schedule(CHANGE)
        expected = {
            "metadata": BSBLANScheduleMappingError,
            "generation": BSBLANScheduleProbeError,
            "permission": BSBLANUnsupportedFeatureError,
        }[change]
        assert isinstance(err.value.__cause__, expected)
        assert len(writes) == 1


@pytest.mark.parametrize("invalidate_profile_cache", [False, True])
async def test_unchanged_target_still_allows_normal_bounded_retry(
    monkeypatch: pytest.MonkeyPatch,
    *,
    invalidate_profile_cache: bool,
) -> None:
    """Adding retry guards must not disable legitimate transport retries."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(manual_config(), session=session)
        client._device = Device(**device(buswritable=1))
        request = Mock(
            side_effect=[
                aiohttp.ClientConnectionError("transient"),
                reply({"700": {"status": 1}}),
            ]
        )
        session.request = request

        async def backoff(_delay: float) -> None:
            if invalidate_profile_cache:
                client.invalidate_schedule_profiles()

        monkeypatch.setattr("backoff._async.asyncio.sleep", backoff)
        await client.set_heating_schedule(CHANGE)
        assert request.call_count == 2
        assert request.call_args_list[0].args[1] == request.call_args_list[1].args[1]


async def test_attempt_guard_is_task_local_and_resets_after_exit() -> None:
    """A blocked protected request must not leak its guard into another task."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(manual_config(), session=session)
        session.request = Mock(side_effect=[reply({}), reply({})])
        start = asyncio.Event()

        async def unprotected_read() -> dict[str, Any]:
            await start.wait()
            return await client._request()

        reader = asyncio.create_task(unprotected_read())
        guard = Mock(side_effect=BSBLANError("blocked"))
        with client._transport.guard_attempts(guard):
            start.set()
            assert await reader == {}
            with pytest.raises(BSBLANError, match="blocked"):
                await client._request()
        assert await client._request() == {}
        assert session.request.call_count == 2
        guard.assert_called_once_with()


async def test_attempt_guard_is_isolated_between_client_instances() -> None:
    """A nested request on another transport must not inherit this client's proof."""
    async with aiohttp.ClientSession() as session:
        first = BSBLAN(manual_config(), session=session)
        other = BSBLAN(manual_config(), session=session)
        session.request = Mock(return_value=reply({}))
        guard = Mock(side_effect=BSBLANError("blocked"))
        with first._transport.guard_attempts(guard):
            assert await other._request() == {}
        guard.assert_not_called()


async def test_cancelled_write_resets_guard_before_followup_read() -> None:
    """Cancellation unwinds the attempt scope before the same task continues."""
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(manual_config(), session=session)
        client._device = Device(**device(buswritable=1))
        started = asyncio.Event()
        never = asyncio.Event()
        pending = MagicMock()

        async def enter() -> Any:
            started.set()
            await never.wait()
            return MagicMock()

        pending.__aenter__.side_effect = enter
        session.request = Mock(side_effect=[pending, reply({})])

        async def worker() -> dict[str, Any]:
            try:
                await client.set_heating_schedule(CHANGE)
            except asyncio.CancelledError:
                client.config.host = "other.example"
                return await client._request()
            message = "Write unexpectedly completed"
            raise AssertionError(message)

        task = asyncio.create_task(worker())
        await started.wait()
        task.cancel()
        assert await task == {}
        assert session.request.call_count == 2
