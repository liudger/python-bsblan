"""Regressions for schedule mapping and parser safety boundaries."""

from datetime import time
from unittest.mock import AsyncMock

import pytest

from bsblan.exceptions import BSBLANError, BSBLANInvalidParameterError
from bsblan.models import DaySchedule, Device, TimeSlot


async def test_unknown_mapping_fails_before_io(mock_bsblan) -> None:
    """An implicit ID-to-weekday assignment is not device evidence."""
    request = AsyncMock(return_value={})
    mock_bsblan._request = request
    with pytest.raises(BSBLANError, match="mapping_unknown"):
        await mock_bsblan.get_hot_water_schedule()
    request.assert_not_awaited()


def test_legacy_parser_semantics() -> None:
    """The public parser retains permissive pre-feature behavior."""
    assert DaySchedule.from_bsblan_format("6:00-7:00").slots == [
        TimeSlot(time(6), time(7))
    ]
    assert DaySchedule.from_bsblan_format("   ").slots == []
    assert DaySchedule.from_bsblan_format(None).slots == []
    with pytest.raises(ValueError, match="Invalid time slot"):
        DaySchedule.from_bsblan_format("##:##-##:##")


async def test_boolean_circuit_rejected_before_io(mock_bsblan) -> None:
    """True must not silently select heating circuit 1."""
    request = AsyncMock(return_value={})
    mock_bsblan._request = request
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.get_heating_schedule(circuit=True)
    request.assert_not_awaited()


async def test_known_pps_is_not_probed(mock_bsblan) -> None:
    """Known PPS is outside this new structured reader's support."""
    mock_bsblan._device = Device.model_construct(bus="PPS")
    request = AsyncMock(return_value={})
    mock_bsblan._request = request
    with pytest.raises(BSBLANError):
        await mock_bsblan.get_hot_water_schedule()
    request.assert_not_awaited()
