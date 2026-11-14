"""General DHW setters cannot bypass the configured schedule writer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from bsblan import SetHotWaterParam

if TYPE_CHECKING:
    from bsblan import BSBLAN


def test_raw_time_program_cannot_bypass_schedule_validation() -> None:
    """The former raw-string route is no longer a writable payload field."""
    invalid: dict[str, Any] = {"dhw_time_programs": "06:00-08:00"}
    with pytest.raises(TypeError, match="dhw_time_programs"):
        SetHotWaterParam(**invalid)


async def test_non_schedule_hot_water_write_remains_available(
    mock_bsblan: BSBLAN,
) -> None:
    """Removing raw schedules does not change ordinary DHW temperature commands."""
    await mock_bsblan.set_hot_water(SetHotWaterParam(nominal_setpoint=55))
    mock_bsblan._request.assert_awaited_once_with(
        base_path="/JS", data={"Parameter": "1610", "Value": "55", "Type": "1"}
    )
