"""Synthetic profile evidence is not a certified real-device weekday mapping."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bsblan import Device, ScheduleMapping, ScheduleMappings
from bsblan import schedule_profiles as profiles
from bsblan._schedule_profiles import ScheduleProfileResolver
from bsblan.exceptions import BSBLANConnectionError, BSBLANMalformedResponseError

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
IDS = ("9001", "9002", "9003", "9004", "9005", "9006", "9007")
MAPPING = ScheduleMapping(**dict(zip(DAYS, IDS, strict=True)))
IDENTITY = {
    "firmware_version": "test-build",
    "bus": "BSB",
    "destination": 0,
    "controller": "TEST-CONTROLLER",
    "family": 211,
    "variant": 127,
    "table": "synthetic-test-table",
}


def entity(value: Any = "06:00-08:00", **changes: Any) -> dict[str, Any]:
    """Build raw API data without claiming live-device evidence."""
    return {
        "name": "test",
        "unit": "",
        "desc": "",
        "error": 0,
        "dataType": 9,
        "value": value,
        **changes,
    }


def profile(**changes: Any) -> profiles.ScheduleProfile:
    """Describe a deliberately synthetic deployment profile."""
    return profiles.ScheduleProfile(
        **{
            "id": "synthetic",
            "evidence": "Synthetic unit test only; not controller evidence",
            "identity": IDENTITY,
            "mappings": ScheduleMappings(heating={1: MAPPING}, hot_water=MAPPING),
            **changes,
        }
    )


def controller_data() -> dict[str, Any]:
    """Return raw controller identity, distinct from adapter firmware."""
    return {
        "6224": entity("TEST-CONTROLLER", dataType=7),
        "6225": entity("211", dataType=0),
        "6226": entity("127", dataType=0),
    }


def probe_data() -> dict[str, Any]:
    """Return all seven candidate parameters."""
    return {param: entity() for param in IDS}


def resolver(
    *,
    registry: tuple[profiles.ScheduleProfile, ...] | None = None,
    table: str | None = "synthetic-test-table",
    identity: dict[str, Any] | None = None,
    probe: Any = None,
    device_changes: dict[str, Any] | None = None,
) -> tuple[ScheduleProfileResolver, AsyncMock, AsyncMock]:
    """Keep the tests at the resolver's request boundary."""
    device = AsyncMock(
        return_value=Device(
            name="Test",
            version="test-build",
            MAC="test",
            uptime=0,
            bus="BSB",
            busdest=0,
        ).model_copy(update=device_changes or {})
    )
    request = AsyncMock(
        side_effect=[
            controller_data() if identity is None else identity,
            probe_data() if probe is None else probe,
        ]
    )
    return (
        ScheduleProfileResolver(
            request=request,
            device=device,
            profiles=(profile(),) if registry is None else registry,
            table=table,
        ),
        request,
        device,
    )


def test_profiles_require_evidence_and_are_immutable() -> None:
    """Profiles cannot accidentally inherit the uncertified example IDs."""
    assert all(p.id != "synthetic" for p in profiles.STANDARD_SCHEDULE_PROFILES)
    supplied = profile()
    assert supplied.identity == profiles.ScheduleProfileIdentity(**IDENTITY)
    with pytest.raises(ValidationError):
        supplied.identity.table = "other"
    for key in ("id", "evidence"):
        with pytest.raises(ValidationError):
            profile(**{key: " "})
    with pytest.raises(ValidationError):
        profile(identity={**IDENTITY, "family": True})
    with pytest.raises(ValidationError):
        profile(mappings=ScheduleMappings())
    for key in ("firmware_version", "controller", "table"):
        with pytest.raises(ValidationError):
            profile(identity={**IDENTITY, key: " "})


async def test_exact_identity_probes_only_the_candidate_ids() -> None:
    """Weekdays come from the profile, never response order or names."""
    subject, request, device = resolver(
        probe=dict(reversed(list(probe_data().items())))
    )
    result = await subject.resolve("heating", 1)
    assert result.availability.enabled
    assert not result.availability.repair_required
    assert not result.availability.retry_required
    assert result.availability.profile_id == "synthetic"
    assert result.availability.source == "profile"
    assert result.mapping == MAPPING
    assert result.response == probe_data()
    device.assert_awaited_once_with()
    assert [call.kwargs for call in request.await_args_list] == [
        {"params": {"Parameter": "6224,6225,6226"}},
        {"params": {"Parameter": ",".join(IDS)}},
    ]


@pytest.mark.parametrize("table", [None, "other-table"])
async def test_table_is_not_inferred_from_matching_firmware(table: str | None) -> None:
    """No active-table assertion means no certified weekday meaning."""
    subject, request, _ = resolver(table=table)
    result = await subject.resolve("heating", 1)
    assert result.availability.status == "unknown"
    assert result.availability.repair_required
    assert result.mapping is None
    assert request.await_count == (0 if table is None else 1)


async def test_empty_registry_never_performs_network_discovery() -> None:
    """Uncertified built-ins do not introduce startup or polling overhead."""
    subject, request, device = resolver(registry=())
    result = await subject.resolve("hot_water", None)
    assert result.availability.reason == "profile_unknown"
    request.assert_not_awaited()
    device.assert_not_awaited()


@pytest.mark.parametrize(
    "change",
    [
        {"version": "other"},
        {"bus": "LPB"},
        {"busdest": 1},
        {"busdest": False},
        {"busdest": 0.0},
        {"bus": None},
        {"busdest": None},
    ],
)
async def test_adapter_identity_mismatch_never_probes_days(
    change: dict[str, Any],
) -> None:
    """Profiles are scoped to bus, destination and exact adapter build."""
    subject, request, _ = resolver(device_changes=change)
    result = await subject.resolve("heating", 1)
    assert result.availability.status == "unknown"
    assert request.await_count <= 1


@pytest.mark.parametrize("param", ["6224", "6225", "6226"])
async def test_controller_identity_mismatch_never_probes_days(param: str) -> None:
    """Same adapter firmware cannot certify a different controller."""
    identity = controller_data()
    identity[param]["value"] = "OTHER" if param == "6224" else "999"
    subject, request, _ = resolver(identity=identity)
    result = await subject.resolve("heating", 1)
    assert result.availability.reason == "profile_unknown"
    assert request.await_count == 1


async def test_ambiguous_profiles_fail_closed_per_group() -> None:
    """Registry order must not decide weekday meaning."""
    subject, request, _ = resolver(registry=(profile(), profile(id="duplicate")))
    result = await subject.resolve("heating", 1)
    assert result.availability.reason == "profile_ambiguous"
    assert result.availability.repair_required
    assert request.await_count == 1


async def test_resolve_many_identifies_once_and_keeps_groups_independent() -> None:
    """Unsupported HC2 does not disable HC1 or hot water."""
    subject, request, device = resolver()
    request.side_effect = [controller_data(), probe_data(), probe_data()]
    results = await subject.resolve_many(
        (("heating", 1), ("heating", 2), ("hot_water", None))
    )
    assert [result.availability.status for result in results] == [
        "enabled",
        "unknown",
        "enabled",
    ]
    assert results[1].availability.reason == "mapping_unknown"
    assert request.await_count == 3
    assert device.await_count == 1


@pytest.mark.parametrize("text", ["06:00-24:00", "22:00-06:00", "##:##-##:##"])
async def test_correct_types_do_not_require_supported_interval_codec(text: str) -> None:
    """Probe compatibility is not a claim about interval codec support."""
    subject, _, _ = resolver(probe={param: entity(text) for param in IDS})
    assert (await subject.resolve("heating", 1)).availability.enabled


@pytest.mark.parametrize("value", [None, "", "---", "None"])
async def test_inactive_probe_requires_retry(value: str | None) -> None:
    """An inactive value is not proof of a wrong mapping."""
    subject, _, _ = resolver(probe={param: entity(value) for param in IDS})
    availability = (await subject.resolve("heating", 1)).availability
    assert availability.retry_required
    assert not availability.repair_required


@pytest.mark.parametrize("error", [42, 256, 261])
async def test_transient_device_errors_require_retry(error: int) -> None:
    """Only a known unsupported-parameter code is a conclusive mismatch."""
    subject, _, _ = resolver(
        probe={param: entity("5", error=error, dataType=0) for param in IDS}
    )
    assert (await subject.resolve("heating", 1)).availability.retry_required


@pytest.mark.parametrize(
    "bad",
    [entity(error=7), entity(dataType=0), entity(dataType=True), entity(dataType="9")],
)
async def test_conclusive_probe_mismatch_disables_the_group(
    bad: dict[str, Any],
) -> None:
    """Every weekday must be present and have exact expected type metadata."""
    response = probe_data()
    response[IDS[-1]] = bad
    subject, _, _ = resolver(probe=response)
    availability = (await subject.resolve("heating", 1)).availability
    assert availability.status == "incompatible"
    assert availability.repair_required
    assert not availability.retry_required


async def test_missing_data_takes_precedence_over_a_possible_mismatch() -> None:
    """An incomplete response is retried rather than saved as a mapping repair."""
    response = {IDS[0]: entity(error=7)}
    subject, _, _ = resolver(probe=response)
    assert (await subject.resolve("heating", 1)).availability.retry_required


@pytest.mark.parametrize(
    "bad", [[], {IDS[0]: None}, {IDS[0]: entity(7)}, {IDS[0]: entity(error=True)}]
)
async def test_malformed_probe_is_not_a_mapping_repair(bad: Any) -> None:
    """Broken responses preserve malformed-response classification."""
    subject, _, _ = resolver(probe=bad)
    with pytest.raises(BSBLANMalformedResponseError):
        await subject.resolve("heating", 1)


async def test_connection_failure_is_not_cached_as_wrong_mapping() -> None:
    """Caller retries can recover using the very same client and profile."""
    subject, request, _ = resolver()
    request.side_effect = [
        controller_data(),
        BSBLANConnectionError(),
        controller_data(),
        probe_data(),
    ]
    with pytest.raises(BSBLANConnectionError):
        await subject.resolve("heating", 1)
    assert (await subject.resolve("heating", 1)).availability.enabled


@pytest.mark.parametrize(
    ("replacement", "status"),
    [
        ({}, "retry"),
        ({"6224": entity(error=7)}, "retry"),
        ({"6224": entity(error=42)}, "retry"),
        ({"6224": entity(None)}, "retry"),
        (
            {
                "6224": entity(error=7),
                "6225": entity("211", dataType=0),
                "6226": entity("127", dataType=0),
            },
            "unknown",
        ),
        (
            {
                "6224": entity("TEST-CONTROLLER", dataType=0),
                "6225": entity("211", dataType=0),
                "6226": entity("127", dataType=0),
            },
            "unknown",
        ),
        (
            {
                "6224": entity("TEST-CONTROLLER", dataType=7),
                "6225": entity("not-a-number", dataType=0),
                "6226": entity("127", dataType=0),
            },
            "unknown",
        ),
    ],
)
async def test_identity_failures_are_conservative(
    replacement: dict[str, Any], status: str
) -> None:
    """Incomplete identity takes precedence over an unsupported fact."""
    subject, request, _ = resolver(identity=replacement)
    availability = (await subject.resolve("heating", 1)).availability
    assert availability.status == status
    assert availability.retry_required is (status == "retry")
    assert request.await_count == 1


@pytest.mark.parametrize(
    "bad", [[], {"6224": None}, {"6224": entity(211)}, {"6224": {"value": "test"}}]
)
async def test_malformed_identity_keeps_response_error(bad: Any) -> None:
    """Malformed identity is not evidence that a different mapping is needed."""
    subject, _, _ = resolver(identity=bad)
    with pytest.raises(BSBLANMalformedResponseError):
        await subject.resolve("heating", 1)


async def test_duplicate_identity_with_disjoint_groups_is_not_ambiguous() -> None:
    """Different evidence profiles can independently certify HC1 and DHW."""
    subject, request, _ = resolver(
        registry=(
            profile(mappings=ScheduleMappings(heating={1: MAPPING})),
            profile(id="dhw-only", mappings=ScheduleMappings(hot_water=MAPPING)),
        )
    )
    request.side_effect = [controller_data(), probe_data(), probe_data()]
    results = await subject.resolve_many((("heating", 1), ("hot_water", None)))
    assert [item.availability.profile_id for item in results] == [
        "synthetic",
        "dhw-only",
    ]


@pytest.mark.parametrize(
    ("param", "digits"),
    [
        ("6225", "\u0662\u0661\u0661"),
        ("6226", "\u0661\u0662\u0667"),
        ("6225", "\uff12\uff11\uff11"),
        ("6226", "\uff11\uff12\uff17"),
    ],
)
async def test_controller_numbers_reject_unicode_digit_lookalikes(
    param: str,
    digits: str,
) -> None:
    """Numeric identity checks intentionally accept ASCII decimal text only."""
    identity = controller_data()
    identity[param]["value"] = digits
    subject, request, _ = resolver(identity=identity)
    result = await subject.resolve("heating", 1)
    assert result.availability.reason == "identity_unsupported"
    assert request.await_count == 1


async def test_multiple_resolutions_are_sequential_and_return_a_tuple() -> None:
    """Keep awaited resolution eager and non-overlapping on a slow bus."""
    hot_water_ids = tuple(str(9101 + index) for index in range(7))
    hot_water = ScheduleMapping(**dict(zip(DAYS, hot_water_ids, strict=True)))
    subject, request, _ = resolver(
        registry=(
            profile(
                mappings=ScheduleMappings(heating={1: MAPPING}, hot_water=hot_water)
            ),
        )
    )
    active = 0
    seen: list[str] = []

    async def handler(**kwargs: Any) -> dict[str, Any]:
        nonlocal active
        active += 1
        try:
            assert active == 1
            parameters = kwargs["params"]["Parameter"]
            seen.append(parameters)
            await asyncio.sleep(0)
            if parameters == "6224,6225,6226":
                return controller_data()
            return {param: entity() for param in parameters.split(",")}
        finally:
            active -= 1

    request.side_effect = handler
    result = await subject.resolve_many((("heating", 1), ("hot_water", None)))
    assert isinstance(result, tuple)
    assert [item.availability.kind for item in result] == ["heating", "hot_water"]
    assert all(item.availability.enabled for item in result)
    assert seen == ["6224,6225,6226", ",".join(IDS), ",".join(hot_water_ids)]
