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
DECIMAL_EVIDENCE = json.loads(load_fixture("rvs21_decimal_schedule_profile.json"))
HC = tuple(EVIDENCE["heating_1"]["ids"])
HC2 = tuple(str(521 + index) for index in range(7))
DHW = tuple(EVIDENCE["hot_water"]["ids"])
HC_DECIMAL = tuple(DECIMAL_EVIDENCE["heating_1"]["ids"])
DHW_DECIMAL = tuple(DECIMAL_EVIDENCE["hot_water"]["ids"])
FR_NAMES = tuple(DECIMAL_EVIDENCE["names"])


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


def structure(
    ids: tuple[str, ...] = HC,
    names: tuple[str, ...] | None = None,
    *,
    decimal: bool = False,
) -> dict[str, Any]:
    """Build a synthetic /JC structure without live program values."""
    selected_names = names or (FR_NAMES if decimal else tuple(EVIDENCE["names"]))
    structure_metadata = {"dataType": 9, "destination": 0, "readwrite": 0}
    return {
        param: {"name": name, **structure_metadata}
        for param, name in zip(ids, selected_names, strict=True)
    }


def values(ids: tuple[str, ...] = HC) -> dict[str, Any]:
    """Use synthetic interval values and explicit permissions in transport tests."""
    return {param: entity("06:00-08:00", readwrite=0) for param in ids}


def integer_profile() -> ScheduleProfile:
    """Select the source-backed integer installation profile."""
    return next(
        profile for profile in STANDARD_SCHEDULE_PROFILES if "integer" in profile.id
    )


def decimal_profile() -> ScheduleProfile:
    """Select the issue-confirmed decimal installation profile."""
    return next(
        profile for profile in STANDARD_SCHEDULE_PROFILES if "decimal" in profile.id
    )


def standard() -> ScheduleProfile:
    """Require the source-backed integer profile."""
    return integer_profile()


def test_standard_profiles_cover_integer_and_decimal_groups() -> None:
    """Protect exact weekday IDs and installation scopes for each profile."""
    assert len(STANDARD_SCHEDULE_PROFILES) == 2

    integer = integer_profile()
    assert integer.identity.model_dump() == EVIDENCE["identity"]
    assert tuple(integer.mappings.heating[1].model_dump().values()) == HC
    assert tuple(integer.mappings.heating[2].model_dump().values()) == HC2
    assert integer.mappings.hot_water is not None
    assert tuple(integer.mappings.hot_water.model_dump().values()) == DHW
    assert dict(integer.table_parameters) == {
        **dict(zip(HC, EVIDENCE["names"], strict=True)),
        **dict(zip(HC2, EVIDENCE["names"], strict=True)),
        **dict(zip(DHW, EVIDENCE["names"], strict=True)),
    }

    decimal = decimal_profile()
    assert decimal.identity.model_dump() == DECIMAL_EVIDENCE["identity"]
    assert tuple(decimal.mappings.heating[1].model_dump().values()) == HC_DECIMAL
    assert tuple(decimal.mappings.heating[2].model_dump().values()) == HC2
    assert decimal.mappings.hot_water is not None
    assert tuple(decimal.mappings.hot_water.model_dump().values()) == DHW_DECIMAL
    assert dict(decimal.table_parameters) == {
        **dict(zip(HC_DECIMAL, FR_NAMES, strict=True)),
        **dict(zip(HC2, FR_NAMES, strict=True)),
        **dict(zip(DHW_DECIMAL, FR_NAMES, strict=True)),
    }
    assert "rvs21" in integer.evidence.lower()
    assert decimal.evidence == "docs/schedule-profiles.md#decimal-rvs21-profile"


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


async def test_integer_discovery_enables_hc1_hc2_and_dhw() -> None:
    """The integer profile supports all three schedule groups."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(),
            controller(),
            structure(HC),
            values(HC),
            structure(HC2),
            values(HC2),
            structure(DHW),
            values(DHW),
        ]
    )
    result = await client.discover_schedules()
    assert [(a.kind, a.circuit, a.status) for a in result] == [
        ("heating", 1, "enabled"),
        ("heating", 2, "enabled"),
        ("hot_water", None, "enabled"),
    ]
    assert [item.profile_id for item in result] == [standard().id] * 3
    assert client.config.schedule_mappings == ScheduleMappings()
    assert client.config.schedule_table is None
    assert [call.kwargs for call in client._request.await_args_list] == [
        {"base_path": "/JI"},
        {"params": {"Parameter": "6224,6225,6226"}},
        {"base_path": "/JC=" + ",".join(HC)},
        {"params": {"Parameter": ",".join(HC)}},
        {"base_path": "/JC=" + ",".join(HC2)},
        {"params": {"Parameter": ",".join(HC2)}},
        {"base_path": "/JC=" + ",".join(DHW)},
        {"params": {"Parameter": ",".join(DHW)}},
    ]


async def test_decimal_discovery_uses_decimal_hc1_dhw_and_integer_hc2() -> None:
    """The issue-scoped profile preserves decimal IDs for HC1 and DHW only."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(version=DECIMAL_EVIDENCE["identity"]["firmware_version"]),
            controller(),
            structure(HC_DECIMAL, decimal=True),
            values(HC_DECIMAL),
            structure(HC2, decimal=True),
            values(HC2),
            structure(DHW_DECIMAL, decimal=True),
            values(DHW_DECIMAL),
        ]
    )
    result = await client.discover_schedules()
    assert [(a.kind, a.circuit, a.status) for a in result] == [
        ("heating", 1, "enabled"),
        ("heating", 2, "enabled"),
        ("hot_water", None, "enabled"),
    ]
    assert [item.profile_id for item in result] == [decimal_profile().id] * 3
    assert [call.kwargs for call in client._request.await_args_list] == [
        {"base_path": "/JI"},
        {"params": {"Parameter": "6224,6225,6226"}},
        {"base_path": "/JC=" + ",".join(HC_DECIMAL)},
        {"params": {"Parameter": ",".join(HC_DECIMAL)}},
        {"base_path": "/JC=" + ",".join(HC2)},
        {"params": {"Parameter": ",".join(HC2)}},
        {"base_path": "/JC=" + ",".join(DHW_DECIMAL)},
        {"params": {"Parameter": ",".join(DHW_DECIMAL)}},
    ]


DECIMAL_PROFILE_GROUPS = (
    ("heating", 1, HC_DECIMAL),
    ("heating", 2, HC2),
    ("hot_water", None, DHW_DECIMAL),
)


@pytest.mark.parametrize(("kind", "circuit", "ids"), DECIMAL_PROFILE_GROUPS)
async def test_decimal_profile_reads_use_group_weekday_ids(
    kind: str, circuit: int | None, ids: tuple[str, ...]
) -> None:
    """Each decimal-profile group reads exactly its configured weekday IDs."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(version=DECIMAL_EVIDENCE["identity"]["firmware_version"]),
            controller(),
            structure(ids, decimal=True),
            values(ids),
        ]
    )
    snapshot = (
        await client.hot_water_schedule()
        if kind == "hot_water"
        else await client.heating_schedule(circuit=circuit or 1)
    )
    assert snapshot.complete
    assert tuple(day.parameter_id for day in snapshot.days) == ids
    assert client._request.await_args_list[-1].kwargs["params"] == {
        "Parameter": ",".join(ids)
    }


@pytest.mark.parametrize(("kind", "circuit", "ids"), DECIMAL_PROFILE_GROUPS)
async def test_decimal_profile_writes_use_group_weekday_ids(
    kind: str, circuit: int | None, ids: tuple[str, ...]
) -> None:
    """Tuesday writes preserve decimal IDs and integer HC2 IDs exactly."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(version=DECIMAL_EVIDENCE["identity"]["firmware_version"]),
            controller(),
            structure(ids, decimal=True),
            values(ids),
            {ids[1]: {"status": 1}},
        ]
    )
    update = ScheduleUpdate(tuesday=DaySchedule.from_bsblan_format("06:00-08:00"))
    if kind == "hot_water":
        await client.set_hot_water_schedule(update)
    else:
        await client.set_heating_schedule(update, circuit=circuit or 1)
    write = client._request.await_args_list[-1]
    assert write.kwargs["data"]["Parameter"] == ids[1]
    assert write.kwargs["base_path"] == "/JS"


@pytest.mark.parametrize(("kind", "circuit", "ids"), DECIMAL_PROFILE_GROUPS)
@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        ("layout_mismatch", BSBLANScheduleMappingError),
        ("layout_incomplete", BSBLANScheduleProbeError),
        ("value_incompatible", BSBLANScheduleMappingError),
    ],
)
async def test_decimal_profile_write_fails_closed_without_js(
    kind: str,
    circuit: int | None,
    ids: tuple[str, ...],
    failure: str,
    expected_error: type[Exception],
) -> None:
    """Bad or incomplete evidence never triggers a schedule write or fallback."""
    table = structure(ids, decimal=True)
    responses: list[dict[str, Any]] = [
        device(version=DECIMAL_EVIDENCE["identity"]["firmware_version"]),
        controller(),
    ]
    if failure == "layout_mismatch":
        table[ids[0]]["name"] = "Wrong weekday"
        responses.append(table)
    elif failure == "layout_incomplete":
        responses.append({})
    else:
        incompatible_values = values(ids)
        incompatible_values[ids[0]]["dataType"] = 0
        responses.extend((table, incompatible_values))
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(side_effect=responses)
    update = ScheduleUpdate(tuesday=DaySchedule.from_bsblan_format("06:00-08:00"))

    operation = (
        client.set_hot_water_schedule(update)
        if kind == "hot_water"
        else client.set_heating_schedule(update, circuit=circuit or 1)
    )
    with pytest.raises(expected_error):
        await operation

    assert all(
        call.kwargs.get("base_path") != "/JS"
        for call in client._request.await_args_list
    )
    assert client._request.await_count == len(responses)


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


async def test_dhw_missing_does_not_disable_known_heating_groups() -> None:
    """A missing DHW definition does not invalidate compatible heating groups."""
    client = BSBLAN(BSBLANConfig(host="example.com"))
    client._request = AsyncMock(
        side_effect=[
            device(),
            controller(),
            structure(HC),
            values(HC),
            structure(HC2),
            values(HC2),
            {},
        ]
    )
    result = await client.discover_schedules()
    assert result[0].enabled
    assert result[1].enabled
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
            structure(HC),
            values(HC),
            structure(HC2),
            values(HC2),
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
    assert client._request.await_count == 14
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
