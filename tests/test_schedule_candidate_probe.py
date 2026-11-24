"""Bounded decimal DHW candidates are diagnostic, never automatic mappings."""

from __future__ import annotations

import json
from datetime import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from pydantic import ValidationError

from bsblan import (
    BSBLAN,
    BSBLANAuthError,
    BSBLANConfig,
    BSBLANConnectionError,
    BSBLANInvalidParameterError,
    BSBLANMalformedResponseError,
    BSBLANScheduleMappingError,
    BSBLANScheduleProbeError,
    BSBLANUnsupportedFeatureError,
    DaySchedule,
    Device,
    ScheduleCandidateProbe,
    ScheduleMappings,
    ScheduleUpdate,
    TimeSlot,
)
from tests.test_schedule_profile_integration import device
from tests.test_schedule_profiles import entity

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer

CANDIDATE = "rvs21_211_127_dhw_decimal"
IDS = ("561", "561.1", "561.2", "561.3", "561.4", "561.5", "561.6")
QUERY = ",".join(IDS)
EVIDENCE = "docs/schedule-profiles.md#decimal-rvs21-profile"


def response() -> dict[str, Any]:
    """Use synthetic values with the issue's exact decimal parameter IDs."""
    return {param: entity() for param in IDS}


def subject() -> BSBLAN:
    """No active table or automatic profile is asserted by this diagnostic."""
    return BSBLAN(BSBLANConfig(host="example.com", schedule_profiles=()))


async def test_exact_bounded_probe_is_compatible_but_never_enables_schedules() -> None:
    """A /JQ success cannot prove the issue's table is active on this device."""
    client = subject()
    client._request = AsyncMock(
        side_effect=[device(), dict(reversed(list(response().items())))]
    )
    result = await client.probe_schedule_candidate(CANDIDATE)
    assert isinstance(result, ScheduleCandidateProbe)
    assert result.candidate_id == CANDIDATE
    assert result.evidence == EVIDENCE
    assert result.kind == "hot_water"
    assert result.status == "compatible"
    assert not result.enabled
    assert result.requires_confirmation
    assert not result.retry_required
    assert not result.incompatible_parameters
    assert not result.retry_parameters
    assert tuple(result.mapping.model_dump().values()) == IDS
    assert result.model_dump(mode="json")["enabled"] is False
    assert result.model_dump(mode="json")["requires_confirmation"] is True
    assert [call.kwargs for call in client._request.await_args_list] == [
        {"base_path": "/JI"},
        {"params": {"Parameter": QUERY}},
    ]
    with pytest.raises(BSBLANScheduleMappingError):
        await client.hot_water_schedule()
    assert client._request.await_count == 2
    for field, value in (
        ("enabled", True),
        ("requires_confirmation", False),
        ("candidate_id", "other"),
    ):
        with pytest.raises(ValidationError):
            setattr(result, field, value)
    with pytest.raises(ValidationError):
        result.mapping.tuesday = "562"


@pytest.mark.parametrize("candidate_id", ["unknown", "", "561"])
async def test_unknown_candidate_is_rejected_before_io(candidate_id: str) -> None:
    """Keep the candidate set finite instead of scanning arbitrary ranges."""
    client = subject()
    client._request = AsyncMock()
    with pytest.raises(BSBLANInvalidParameterError):
        await client.probe_schedule_candidate(candidate_id)
    client._request.assert_not_awaited()


@pytest.mark.parametrize("bus", ["BSB", "LPB"])
async def test_candidate_requires_explicit_supported_bus(bus: str) -> None:
    """Both supported bus types can be diagnosed without asserting a profile."""
    client = subject()
    client._request = AsyncMock(side_effect=[device(bus=bus), response()])
    assert (await client.probe_schedule_candidate(CANDIDATE)).status == "compatible"


@pytest.mark.parametrize("bus", ["PPS", None, "unknown"])
async def test_new_unsupported_bus_does_not_read_candidate_ids(bus: str | None) -> None:
    """Missing bus evidence must not be interpreted as implicit BSB compatibility."""
    client = subject()
    client._request = AsyncMock(return_value=device(bus=bus))
    with pytest.raises(BSBLANUnsupportedFeatureError):
        await client.probe_schedule_candidate(CANDIDATE)
    client._request.assert_awaited_once_with(base_path="/JI")


async def test_known_pps_is_rejected_without_network_requests() -> None:
    """Do not even refresh adapter metadata for a known unsupported bus."""
    client = subject()
    client._device = Device(**device(bus="PPS"))
    client._request = AsyncMock()
    with pytest.raises(BSBLANUnsupportedFeatureError):
        await client.probe_schedule_candidate(CANDIDATE)
    client._request.assert_not_awaited()


@pytest.mark.parametrize(
    "bad",
    [entity(dataType=0), entity(dataType=True), entity(dataType="9"), entity(error=7)],
)
async def test_incompatible_candidate_reports_exact_parameter_without_enabling(
    bad: dict[str, Any],
) -> None:
    """The caller can see the failing decimal ID without guessing another mapping."""
    client = subject()
    data = response()
    data["561.4"] = bad
    client._request = AsyncMock(side_effect=[device(), data])
    result = await client.probe_schedule_candidate(CANDIDATE)
    assert result.status == "incompatible"
    assert result.incompatible_parameters == ("561.4",)
    assert not result.retry_parameters
    assert not result.retry_required
    assert not result.enabled


@pytest.mark.parametrize("value", [None, "", "---", "None"])
async def test_inactive_candidate_is_retryable(value: str | None) -> None:
    """Inactive values cannot conclusively prove a wrong table."""
    client = subject()
    client._request = AsyncMock(
        side_effect=[device(), {param: entity(value) for param in IDS}]
    )
    result = await client.probe_schedule_candidate(CANDIDATE)
    assert result.retry_required
    assert result.retry_parameters == IDS
    assert not result.enabled


async def test_missing_and_transient_candidate_data_precedes_incompatibility() -> None:
    """Keep parameter-level outcomes but never diagnose a partial response as wrong."""
    client = subject()
    client._request = AsyncMock(
        side_effect=[
            device(),
            {
                "561": entity(error=7),
                "561.1": entity(error=42),
            },
        ]
    )
    result = await client.probe_schedule_candidate(CANDIDATE)
    assert result.status == "retry"
    assert result.incompatible_parameters == ("561",)
    assert result.retry_parameters == IDS[1:]


@pytest.mark.parametrize(
    "bad", [[], {"561": None}, {"561": entity(7)}, {"561": entity(error=True)}]
)
async def test_malformed_candidate_data_keeps_its_exception(bad: Any) -> None:
    """Malformed responses must not be converted into a mapping repair result."""
    client = subject()
    client._request = AsyncMock(side_effect=[device(), bad])
    with pytest.raises(BSBLANMalformedResponseError):
        await client.probe_schedule_candidate(CANDIDATE)


@pytest.mark.parametrize("error", [BSBLANConnectionError, BSBLANAuthError])
async def test_candidate_transport_errors_propagate_and_later_attempt_can_recover(
    error: type[Exception],
) -> None:
    """Only an explicit subsequent call retries the bounded candidate probe."""
    client = subject()
    client._request = AsyncMock(side_effect=[device(), error(), device(), response()])
    with pytest.raises(error):
        await client.probe_schedule_candidate(CANDIDATE)
    assert (await client.probe_schedule_candidate(CANDIDATE)).status == "compatible"
    assert client._request.await_count == 4


@pytest.mark.parametrize("stage", [0, 1])
async def test_target_change_during_candidate_probe_is_rejected(stage: int) -> None:
    """A diagnostic result must stay bound to the captured transport target."""
    client = subject()
    replies = [device(), response()]
    seen: list[dict[str, Any]] = []

    async def request(**kwargs: Any) -> Any:
        index = len(seen)
        seen.append(kwargs)
        if index == stage:
            client.config.host = "other.example"
        return replies[index]

    client._request = request
    with pytest.raises(BSBLANScheduleMappingError):
        await client.probe_schedule_candidate(CANDIDATE)
    assert len(seen) == stage + 1


async def test_confirmed_manual_override_writes_decimal_weekdays() -> None:
    """Independently confirmed overrides fix Tuesday/Sunday without integer fallback."""
    diagnostic = subject()
    diagnostic._request = AsyncMock(side_effect=[device(), response()])
    result = await diagnostic.probe_schedule_candidate(CANDIDATE)
    # This separate configuration represents the caller confirming active-table
    # evidence, not the probe automatically enabling or promoting a candidate.
    client = BSBLAN(
        BSBLANConfig(
            host="example.com",
            schedule_mappings=ScheduleMappings(hot_water=result.mapping),
        )
    )
    client._request = AsyncMock(
        side_effect=[{"561.1": {"status": 1}}, {"561.6": {"status": 1}}]
    )
    day = DaySchedule((TimeSlot(time(6), time(8)),))
    await client.set_hot_water_schedule(ScheduleUpdate(tuesday=day, sunday=day))
    assert [call.kwargs for call in client._request.await_args_list] == [
        {
            "base_path": "/JS",
            "data": {"Parameter": "561.1", "Value": "06:00-08:00", "Type": "1"},
        },
        {
            "base_path": "/JS",
            "data": {"Parameter": "561.6", "Value": "06:00-08:00", "Type": "1"},
        },
    ]


async def test_decimal_probe_real_http_boundary(
    aresponses: ResponsesMockServer,
) -> None:
    """The actual transport sends only /JI then one exact seven-ID /JQ request."""
    seen: list[tuple[str, str | None]] = []

    async def handler(request: Any) -> Any:
        seen.append((request.path, request.query.get("Parameter")))
        data = device() if request.path == "/JI" else response()
        return aresponses.Response(text=json.dumps(data))

    aresponses.add("example.com", "/JI", "POST", handler)
    aresponses.add("example.com", "/JQ", "POST", handler)
    async with aiohttp.ClientSession() as session:
        client = subject()
        client.session = session
        result = await client.probe_schedule_candidate(CANDIDATE)
    assert result.status == "compatible"
    assert not result.enabled
    assert seen == [("/JI", None), ("/JQ", QUERY)]


async def test_invalidated_candidate_work_returns_no_stale_result() -> None:
    """Explicit invalidation during a diagnostic await requests a later retry."""
    client = subject()

    async def request(**kwargs: Any) -> Any:
        if kwargs.get("base_path") == "/JI":
            return device()
        client.invalidate_schedule_profiles()
        return response()

    client._request = request
    with pytest.raises(BSBLANScheduleProbeError, match="discovery_invalidated"):
        await client.probe_schedule_candidate(CANDIDATE)
