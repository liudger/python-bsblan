"""Tests for DHW time switch functionality."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from unittest.mock import AsyncMock

import pytest

from bsblan import BSBLAN, BSBLANError
from bsblan.constants import MULTI_PARAMETER_ERROR_MSG


@pytest.mark.asyncio
async def test_set_dhw_time_program(mock_bsblan: BSBLAN) -> None:
    """Test setting DHW time program.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test setting time program for Monday
    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_hot_water(dhw_time_program_monday="13:00-14:00 ##:##-##:## ##:##-##:##")
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "561",
            "Value": "13:00-14:00 ##:##-##:## ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Tuesday
    await mock_bsblan.set_hot_water(dhw_time_program_tuesday="06:00-08:00 17:00-20:00 ##:##-##:##")
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "562",
            "Value": "06:00-08:00 17:00-20:00 ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Wednesday
    await mock_bsblan.set_hot_water(dhw_time_program_wednesday="07:30-09:00 18:00-21:30 ##:##-##:##")
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "563",
            "Value": "07:30-09:00 18:00-21:30 ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Thursday
    await mock_bsblan.set_hot_water(dhw_time_program_thursday="06:00-09:00 16:00-22:00 ##:##-##:##")
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "564",
            "Value": "06:00-09:00 16:00-22:00 ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Friday
    await mock_bsblan.set_hot_water(dhw_time_program_friday="06:00-09:00 15:00-23:00 ##:##-##:##")
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "565",
            "Value": "06:00-09:00 15:00-23:00 ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Saturday
    await mock_bsblan.set_hot_water(dhw_time_program_saturday="08:00-23:00 ##:##-##:## ##:##-##:##")
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "566",
            "Value": "08:00-23:00 ##:##-##:## ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Sunday
    await mock_bsblan.set_hot_water(dhw_time_program_sunday="08:00-22:00 ##:##-##:## ##:##-##:##")
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "567",
            "Value": "08:00-22:00 ##:##-##:## ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting standard values
    await mock_bsblan.set_hot_water(dhw_time_program_standard_values="0")
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "576",
            "Value": "0",
            "Type": "1",
        },
    )

    # Test setting multiple parameters (should raise an error)
    with pytest.raises(BSBLANError, match=MULTI_PARAMETER_ERROR_MSG):
        await mock_bsblan.set_hot_water(
            dhw_time_program_monday="13:00-14:00 ##:##-##:## ##:##-##:##", 
            dhw_time_program_tuesday="06:00-08:00 17:00-20:00 ##:##-##:##",
        )


@pytest.mark.asyncio
async def test_prepare_dhw_time_program_state(mock_bsblan: BSBLAN) -> None:
    """Test preparing DHW time program state.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test preparing Monday time program
    state = mock_bsblan._prepare_hot_water_state(
        nominal_setpoint=None,
        reduced_setpoint=None,
        operating_mode=None,
        dhw_time_program_monday="13:00-14:00 ##:##-##:## ##:##-##:##",
    )
    assert state == {
        "Parameter": "561",
        "Value": "13:00-14:00 ##:##-##:## ##:##-##:##",
        "Type": "1",
    }

    # Test preparing Tuesday time program
    state = mock_bsblan._prepare_hot_water_state(
        nominal_setpoint=None,
        reduced_setpoint=None,
        operating_mode=None,
        dhw_time_program_tuesday="06:00-08:00 17:00-20:00 ##:##-##:##",
    )
    assert state == {
        "Parameter": "562",
        "Value": "06:00-08:00 17:00-20:00 ##:##-##:##",
        "Type": "1",
    }

    # Test preparing standard values
    state = mock_bsblan._prepare_hot_water_state(
        nominal_setpoint=None,
        reduced_setpoint=None,
        operating_mode=None,
        dhw_time_program_standard_values="0",
    )
    assert state == {
        "Parameter": "576",
        "Value": "0",
        "Type": "1",
    }