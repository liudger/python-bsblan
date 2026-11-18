"""Source-backed profile selection uses predefined roles, never label inference."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bsblan import (
    BSBLAN,
    STANDARD_SCHEDULE_PROFILES,
    BSBLANConfig,
    BSBLANConnectionError,
    BSBLANMalformedResponseError,
    BSBLANScheduleMappingError,
    BSBLANScheduleProbeError,
    DaySchedule,
    ScheduleMappings,
    ScheduleProfile,
    ScheduleUpdate,
)
from tests import load_fixture
from tests.test_schedule_profiles import entity

EVIDENCE = json.loads(load_fixture("rvs21_schedule_profile.json"))
HC = tuple(EVIDENCE["heating_1"]["ids"])
DHW = tuple(EVIDENCE["hot_water"]["ids"])


def device(**changes: Any) -> dict[str, Any]:
    """Use a synthetic MAC/uptime with the verified public installation scope."""
    return {
        "name": "test",
        "version": EVIDENCE["identity"]["firmware_version"],
        "MAC": "test",
        "uptime": 0,
        "bus": "BSB",
        "busdest": 0,
        "buswritable": 0,
        **changes,
    }


def controller(**changes: str) -> dict[str, Any]:
    """Build raw scope data independently of adapter version."""
    return {
        "6224": entity(changes.get("controller", "RVS21.831F/127"), dataType=7),
        "6225": entity(changes.get("family", "211"), dataType=0),
        "6226": entity(changes.get("variant", "127"), dataType=0),
    }


def structure(ids: tuple[str, ...] = HC) -> dict[str, Any]:
    """Reproduce the observed static structure, without live program values."""
    return {
        param: {"name": name, **EVIDENCE["observed_structure"]}
        for param, name in zip(ids, EVIDENCE["names"], strict=True)
    }


def values(ids: tuple[str, ...] = HC) -> dict[str, Any]:
    """Use synthetic interval values and explicit permissions in transport tests."""
    return {param: entity("06:00-08:00", readwrite=0) for param in ids}


def standard() -> ScheduleProfile:
    """Require the real verified profile, not a supplied manual mapping."""
    return STANDARD_SCHEDULE_PROFILES[0]


def test_first_profile_has_source_backed_scope_and_roles() -> None:
    """Protect literal integer assignments from the decimal scheme in issue #1668."""
    assert len(STANDARD_SCHEDULE_PROFILES) == 1
    profile = standard()
    assert profile.identity.model_dump() == EVIDENCE["identity"]
    assert tuple(profile.mappings.heating[1].model_dump().values()) == HC
    assert profile.mappings.hot_water is not None
    assert tuple(profile.mappings.hot_water.model_dump().values()) == DHW
    assert 2 not in profile.mappings.heating
    assert dict(profile.table_parameters) == {
        **dict(zip(HC, EVIDENCE["names"], strict=True)),
        **dict(zip(DHW, EVIDENCE["names"], strict=True)),
    }
    assert "rvs21" in profile.evidence.lower()


@pytest.mark.parametrize("bad", [(), (("501", "Monday"),), (("501", " "),)])
def test_incomplete_or_blank_declared_signature_is_rejected_except_empty(
    bad: Any,
) -> None:
    """A nonempty signature must certify every mapped ID exactly once."""
    data = standard().model_dump()
    data["table_parameters"] = bad
    if not bad:
        assert ScheduleProfile.model_validate(data).table_parameters == ()
    else:
        with pytest.raises(ValidationError):
            ScheduleProfile.model_validate(data)


async def test_default_discovery_selects_profile_without_manual_table_or_mapping() -> (
    None
):
    """Default discovery recognizes HC1 and DHW; HC2 remains independently unknown."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(),
            controller(),
            structure(),
            values(),
            structure(DHW),
            values(DHW),
        ]
    )
    result = await client.discover_schedules()
    assert [(a.kind, a.circuit, a.status) for a in result] == [
        ("heating", 1, "enabled"),
        ("heating", 2, "unknown"),
        ("hot_water", None, "enabled"),
    ]
    assert result[0].source == "profile"
    assert result[0].profile_id == standard().id
    assert client.config.schedule_mappings == ScheduleMappings()
    assert client.config.schedule_table is None
    assert [c.kwargs for c in client._request.await_args_list] == [
        {"base_path": "/JI"},
        {"params": {"Parameter": "6224,6225,6226"}},
        {"base_path": "/JC=" + ",".join(HC)},
        {"params": {"Parameter": ",".join(HC)}},
        {"base_path": "/JC=" + ",".join(DHW)},
        {"params": {"Parameter": ",".join(DHW)}},
    ]


@pytest.mark.parametrize(
    "change", [{"version": "5.1.1-other-build"}, {"bus": "LPB"}, {"busdest": 1}]
)
async def test_unverified_scope_never_probes_schedule_ids(
    change: dict[str, Any],
) -> None:
    """A compatible-looking table cannot broaden a controller/build certification."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(side_effect=[device(**change), controller()])
    result = await client.discover_schedules()
    assert all(not a.enabled for a in result)
    assert client._request.await_count == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "Tuesday"),
        ("dataType", 0),
        ("dataType", True),
        ("destination", 1),
        ("destination", False),
    ],
)
async def test_wrong_active_structure_is_not_enabled(field: str, value: Any) -> None:
    """Do not accept a wrong weekday label, type or destination under this profile."""
    raw = structure()
    raw[HC[0]][field] = value
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(side_effect=[device(), controller(), raw])
    with pytest.raises(BSBLANScheduleMappingError) as err:
        await client.heating_schedule()
    assert err.value.reason == "table_incompatible"
    assert client._request.await_count == 3


@pytest.mark.parametrize(
    "raw", [{}, {"501": {"name": "Monday"}}, {"501": {"error": 42}}]
)
async def test_incomplete_table_is_retryable_not_mapping_repair(raw: Any) -> None:
    """An incomplete static response is not evidence that weekday roles are wrong."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(side_effect=[device(), controller(), raw])
    with pytest.raises(BSBLANScheduleProbeError, match="table_incomplete"):
        await client.heating_schedule()


@pytest.mark.parametrize("raw", [[], {"501": None}, {"501": {"error": True}}])
async def test_malformed_table_keeps_response_classification(raw: Any) -> None:
    """Non-object structure envelopes/entities do not create mapping repairs."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(side_effect=[device(), controller(), raw])
    with pytest.raises(BSBLANMalformedResponseError):
        await client.heating_schedule()


async def test_structure_connection_failure_remains_retryable() -> None:
    """Network failures do not select a different profile or persist a mismatch."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(),
            controller(),
            BSBLANConnectionError(),
            device(),
            controller(),
            structure(),
            values(),
        ]
    )
    with pytest.raises(BSBLANConnectionError):
        await client.heating_schedule()
    assert (await client.heating_schedule()).complete


async def test_hcw_missing_does_not_disable_known_heating_group() -> None:
    """A missing DHW definition does not invalidate a compatible HC1 table."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[device(), controller(), structure(), values(), {}]
    )
    result = await client.discover_schedules()
    assert result[0].enabled
    assert result[2].retry_required


async def test_explicit_table_assertion_cannot_be_silently_overridden() -> None:
    """Never override an explicit incompatible table assertion."""
    client = BSBLAN(BSBLANConfig(host="example.com", schedule_table="different-table"))
    client._request = AsyncMock(side_effect=[device(), controller()])
    result = await client.discover_schedules()
    assert all(not a.enabled for a in result)
    assert client._request.await_count == 2


async def test_ambiguous_signature_profiles_fail_closed_and_share_jc_probe() -> None:
    """Equivalent source scopes do not become safe just by choosing registry order."""
    other = standard().model_copy(update={"id": "another-source"})
    client = BSBLAN(
        BSBLANConfig(host="example.com", schedule_profiles=(standard(), other))
    )
    client._request = AsyncMock(side_effect=[device(), controller(), structure()])
    with pytest.raises(BSBLANScheduleMappingError) as err:
        await client.heating_schedule()
    assert err.value.reason == "profile_ambiguous"
    assert client._request.await_count == 3


@pytest.mark.parametrize("variant", ["duplicate", "blank"])
def test_declared_signature_cannot_duplicate_ids_or_use_blank_names(
    variant: str,
) -> None:
    """Reject incorrect certification data even when all other fields are valid."""
    data = standard().model_dump()
    signature = data["table_parameters"]
    data["table_parameters"] = (
        (*signature, signature[0])
        if variant == "duplicate"
        else ((signature[0][0], " "), *signature[1:])
    )
    with pytest.raises(ValidationError, match="exactly once"):
        ScheduleProfile.model_validate(data)


async def test_explicit_unsupported_structure_does_not_enable_a_profile() -> None:
    """An unsupported parameter is a complete incompatibility, not a match."""
    raw = structure()
    raw[HC[0]]["error"] = 7
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(side_effect=[device(), controller(), raw])
    with pytest.raises(BSBLANScheduleMappingError, match="table_incompatible"):
        await client.heating_schedule()


async def test_layout_change_invalidates_cached_group_proofs() -> None:
    """An old successful table probe must not survive a changed active definition."""
    changed = structure()
    changed[HC[0]]["name"] = "Different weekday role"
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(),
            controller(),
            structure(),
            values(),
            structure(DHW),
            values(DHW),
            device(),
            controller(),
            changed,
            device(),
            controller(),
            changed,
        ]
    )
    await client.discover_schedules()
    with pytest.raises(BSBLANScheduleProbeError, match="discovery_invalidated"):
        await client.set_heating_schedule(
            ScheduleUpdate(monday=DaySchedule.from_bsblan_format("07:00-09:00"))
        )
    with pytest.raises(BSBLANScheduleMappingError, match="table_incompatible"):
        await client.heating_schedule()
    assert client._request.await_count == 12
    assert all(
        c.kwargs.get("base_path") != "/JS" for c in client._request.await_args_list
    )


async def test_incomplete_competitor_prevents_selecting_a_compatible_candidate() -> (
    None
):
    """Do not certify uniqueness while another eligible source is inconclusive."""
    original = standard()
    alternate = ScheduleProfile.model_validate(
        {
            **original.model_dump(),
            "id": "alternate",
            "table_parameters": tuple(
                (p, n + " alt") for p, n in original.table_parameters
            ),
        }
    )
    client = BSBLAN(
        BSBLANConfig(host="example.com", schedule_profiles=(original, alternate))
    )
    client._request = AsyncMock(side_effect=[device(), controller(), structure(), {}])
    with pytest.raises(BSBLANScheduleProbeError, match="table_incomplete"):
        await client.heating_schedule()
    assert client._request.await_count == 4
