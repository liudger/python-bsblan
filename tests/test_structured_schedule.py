"""Synthetic tests for fresh structured schedule snapshots."""

from __future__ import annotations

from datetime import UTC, time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from bsblan.exceptions import (
    BSBLANError,
    BSBLANInvalidParameterError,
    BSBLANMalformedResponseError,
)
from bsblan.models import (
    DaySchedule,
    ScheduleReadMapping,
    TimeSlot,
)

if TYPE_CHECKING:
    from bsblan import BSBLAN


def configured(first: int) -> ScheduleReadMapping:
    """Use a synthetic integer mapping, not a firmware profile claim."""
    return ScheduleReadMapping(
        monday=str(first),
        tuesday=str(first + 1),
        wednesday=str(first + 2),
        thursday=str(first + 3),
        friday=str(first + 4),
        saturday=str(first + 5),
        sunday=str(first + 6),
    )


def entity(value: Any, *, error: int = 0, data_type: Any = 9) -> dict[str, Any]:
    """Construct an entirely synthetic response entity."""
    return {
        "name": "Program",
        "value": value,
        "unit": "",
        "desc": "",
        "error": error,
        "dataType": data_type,
    }


@pytest.mark.parametrize(
    ("kind", "circuit", "first"),
    [("hot_water", None, 561), ("heating", 1, 501), ("heating", 2, 521)],
)
async def test_mapping_and_fresh_reads(
    mock_bsblan: BSBLAN,
    kind: str,
    circuit: int | None,
    first: int,
) -> None:
    """Requests use the day IDs and reordered data stays correctly mapped."""
    request = AsyncMock(
        side_effect=[
            {
                str(first + 1): entity("09:00-10:00"),
                str(first): entity("06:00-08:00 ##:##-##:##"),
            },
            {str(first): entity("10:00-11:00"), str(first + 1): entity("##:##-##:##")},
        ]
    )
    mock_bsblan._request = request
    if kind == "hot_water":
        one = await mock_bsblan.get_hot_water_schedule(mapping=configured(first))
        two = await mock_bsblan.get_hot_water_schedule(mapping=configured(first))
    else:
        assert circuit is not None
        one = await mock_bsblan.get_heating_schedule(
            circuit=circuit, mapping=configured(first)
        )
        two = await mock_bsblan.get_heating_schedule(
            circuit=circuit, mapping=configured(first)
        )
    assert one.kind == kind
    assert one.circuit == circuit
    assert one.source == "device_response"
    assert one.received_at.tzinfo == UTC
    assert one.days["monday"].parameter_id == str(first)
    assert one.days["monday"].schedule.slots == [TimeSlot(time(6), time(8))]
    assert one.days["tuesday"].schedule.slots == [TimeSlot(time(9), time(10))]
    assert one.days["wednesday"].status == "unavailable"
    assert not one.complete
    assert two.days["monday"].schedule.slots == [TimeSlot(time(10), time(11))]
    assert two.days["tuesday"].status == "empty"
    assert two.days["tuesday"].schedule.slots == []
    assert request.await_count == 2
    for call in request.await_args_list:
        expected = ",".join(str(first + n) for n in range(7))
        assert call.kwargs == {"params": {"Parameter": expected}}


async def test_complete_and_sentinels(mock_bsblan: BSBLAN) -> None:
    """Unavailable sentinels never turn into clearable days."""
    data = {str(501 + n): entity("##:##-##:##") for n in range(7)}
    mock_bsblan._request = AsyncMock(return_value=data)
    result = await mock_bsblan.get_heating_schedule(mapping=configured(501))
    assert result.complete
    assert all(day.status == "empty" for day in result.days.values())
    for value in (None, "", "---", "None"):
        data["502"] = entity(value)
        result = await mock_bsblan.get_heating_schedule(mapping=configured(501))
        day = result.days["tuesday"]
        assert not result.complete
        assert day.status == "unavailable"
        assert day.raw_value == value
        assert day.schedule is None


@pytest.mark.parametrize(
    "value",
    [
        "06:00-##:##",
        "06:00-24:00",
        "22:00-06:00",
        "06:00-06:00",
        "06:00:00-07:00",
        "6:00-07:00",
        "##:##-##:## " * 4,
        "06:00-08:00 07:00-09:00",
        "06:00-08:00 06:00-08:00",
        0,
        [],
        "   ",
    ],
)
async def test_bad_values_are_contextual(mock_bsblan: BSBLAN, value: Any) -> None:
    """Invalid schedules cannot become empty or partially writable."""
    mock_bsblan._request = AsyncMock(return_value={"501": entity(value)})
    with pytest.raises(BSBLANMalformedResponseError, match=r"monday.*501") as exc:
        await mock_bsblan.get_heating_schedule(mapping=configured(501))
    assert exc.value.__cause__ is not None


def test_day_parser_roundtrip() -> None:
    """The public parser retains its original active-slot behavior."""
    parsed = DaySchedule.from_bsblan_format("06:00-08:00 17:00-21:00")
    assert parsed.slots == [TimeSlot(time(6), time(8)), TimeSlot(time(17), time(21))]
    assert DaySchedule.from_bsblan_format(parsed.to_bsblan_format()) == parsed


async def test_error_classification(mock_bsblan: BSBLAN) -> None:
    """Unsupported evidence differs from missing data or other device errors."""
    mock_bsblan._request = AsyncMock(
        return_value={str(501 + n): entity("---", error=7) for n in range(7)}
    )
    result = await mock_bsblan.get_heating_schedule(mapping=configured(501))
    assert all(day.error_code == 7 for day in result.days.values())
    for response in (
        {},
        {"516": entity("0")},
        {"501": entity("---", error=7)},
        {"501": entity("06:00-08:00", error=261)},
    ):
        mock_bsblan._request = AsyncMock(return_value=response)
        result = await mock_bsblan.get_heating_schedule(mapping=configured(501))
        assert not result.complete
        assert all(day.status == "unavailable" for day in result.days.values())
    mock_bsblan._request = AsyncMock(
        return_value={
            "501": entity("06:00-08:00"),
            "502": entity("---", error=7),
            "503": entity("---", error=261),
        }
    )
    result = await mock_bsblan.get_heating_schedule(mapping=configured(501))
    assert result.days["tuesday"].status == "unavailable"
    assert result.days["wednesday"].metadata.error == 261


@pytest.mark.parametrize(
    "bad",
    [
        entity("06:00-08:00", data_type=0),
        entity("06:00-08:00", data_type=None),
        {"value": "06:00-08:00", "dataType": 9},
        None,
        {"name": "x", "unit": "", "desc": "", "dataType": 9},
    ],
)
async def test_bad_entities(mock_bsblan: BSBLAN, bad: Any) -> None:
    """Malformed metadata, unsupported types and absent values fail closed."""
    mock_bsblan._request = AsyncMock(return_value={"501": bad})
    with pytest.raises(BSBLANMalformedResponseError, match=r"monday.*501") as exc:
        await mock_bsblan.get_heating_schedule(mapping=configured(501))
    assert exc.value.__cause__ is not None


async def test_raw_heating_reader_unchanged(mock_bsblan: BSBLAN) -> None:
    """The legacy EntityInfo reader remains separate."""
    mock_bsblan._request = AsyncMock(return_value={"501": entity("06:00-08:00")})
    raw = await mock_bsblan.read_parameters(["501"])
    assert raw["501"].value == "06:00-08:00"


async def test_invalid_circuit_and_invalid_response(mock_bsblan: BSBLAN) -> None:
    """Invalid circuits and malformed response envelopes fail before use."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.get_heating_schedule(circuit=3)
    with pytest.raises(BSBLANError, match="circuit is required"):
        await mock_bsblan._schedules.structured_schedule("heating")
    mock_bsblan._request = AsyncMock(return_value=[])
    with pytest.raises(BSBLANMalformedResponseError):
        await mock_bsblan.get_hot_water_schedule(mapping=configured(561))
    mock_bsblan._request = AsyncMock(return_value={"561": entity("invalid")})
    with pytest.raises(BSBLANMalformedResponseError, match=r"monday.*561"):
        await mock_bsblan.get_hot_water_schedule(mapping=configured(561))


async def test_incomplete_then_present(mock_bsblan: BSBLAN) -> None:
    """Missing days are requested again and may become available."""
    mock_bsblan._request = AsyncMock(
        side_effect=[
            {"561": entity("06:00-08:00")},
            {"561": entity("06:00-08:00"), "562": entity("07:00-09:00")},
        ]
    )
    first = await mock_bsblan.get_hot_water_schedule(mapping=configured(561))
    second = await mock_bsblan.get_hot_water_schedule(mapping=configured(561))
    assert first.days["tuesday"].status == "unavailable"
    assert second.days["tuesday"].status == "readable"
    assert second.days["monday"].raw_value == "06:00-08:00"
    assert second.model_dump(mode="json")["days"]["tuesday"]["schedule"]["slots"] == [
        {"start": "07:00:00", "end": "09:00:00"}
    ]
