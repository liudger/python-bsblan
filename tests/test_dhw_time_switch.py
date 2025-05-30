"""Tests for DHW time switch functionality."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from unittest.mock import AsyncMock

import pytest

from bsblan import BSBLAN, BSBLANError
from bsblan.constants import MULTI_PARAMETER_ERROR_MSG
from bsblan.models import DHWTimeSwitchPrograms


@pytest.mark.asyncio
async def test_set_dhw_time_program(mock_bsblan: BSBLAN) -> None:
    """Test setting DHW time program.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test setting time program for Monday
    assert isinstance(mock_bsblan._request, AsyncMock)
    dhw_programs = DHWTimeSwitchPrograms(monday="13:00-14:00 ##:##-##:## ##:##-##:##")
    await mock_bsblan.set_hot_water(dhw_time_programs=dhw_programs)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "561",
            "Value": "13:00-14:00 ##:##-##:## ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Tuesday
    dhw_programs = DHWTimeSwitchPrograms(tuesday="06:00-08:00 17:00-20:00 ##:##-##:##")
    await mock_bsblan.set_hot_water(dhw_time_programs=dhw_programs)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "562",
            "Value": "06:00-08:00 17:00-20:00 ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Wednesday
    dhw_programs = DHWTimeSwitchPrograms(
        wednesday="07:30-09:00 18:00-21:30 ##:##-##:##"
    )
    await mock_bsblan.set_hot_water(dhw_time_programs=dhw_programs)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "563",
            "Value": "07:30-09:00 18:00-21:30 ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Thursday
    dhw_programs = DHWTimeSwitchPrograms(thursday="06:00-09:00 16:00-22:00 ##:##-##:##")
    await mock_bsblan.set_hot_water(dhw_time_programs=dhw_programs)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "564",
            "Value": "06:00-09:00 16:00-22:00 ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Friday
    dhw_programs = DHWTimeSwitchPrograms(friday="06:00-09:00 15:00-23:00 ##:##-##:##")
    await mock_bsblan.set_hot_water(dhw_time_programs=dhw_programs)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "565",
            "Value": "06:00-09:00 15:00-23:00 ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Saturday
    dhw_programs = DHWTimeSwitchPrograms(saturday="08:00-23:00 ##:##-##:## ##:##-##:##")
    await mock_bsblan.set_hot_water(dhw_time_programs=dhw_programs)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "566",
            "Value": "08:00-23:00 ##:##-##:## ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting time program for Sunday
    dhw_programs = DHWTimeSwitchPrograms(sunday="08:00-22:00 ##:##-##:## ##:##-##:##")
    await mock_bsblan.set_hot_water(dhw_time_programs=dhw_programs)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "567",
            "Value": "08:00-22:00 ##:##-##:## ##:##-##:##",
            "Type": "1",
        },
    )

    # Test setting standard values
    dhw_programs = DHWTimeSwitchPrograms(standard_values="0")
    await mock_bsblan.set_hot_water(dhw_time_programs=dhw_programs)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "576",
            "Value": "0",
            "Type": "1",
        },
    )

    # Test setting multiple parameters (should raise an error)
    dhw_programs = DHWTimeSwitchPrograms(
        monday="13:00-14:00 ##:##-##:## ##:##-##:##",
        tuesday="06:00-08:00 17:00-20:00 ##:##-##:##",
    )
    with pytest.raises(BSBLANError, match=MULTI_PARAMETER_ERROR_MSG):
        await mock_bsblan.set_hot_water(dhw_time_programs=dhw_programs)


@pytest.mark.asyncio
async def test_prepare_dhw_time_program_state(mock_bsblan: BSBLAN) -> None:
    """Test preparing DHW time program state.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test preparing Monday time program
    dhw_programs = DHWTimeSwitchPrograms(monday="13:00-14:00 ##:##-##:## ##:##-##:##")
    state = mock_bsblan._prepare_hot_water_state(
        nominal_setpoint=None,
        reduced_setpoint=None,
        operating_mode=None,
        dhw_time_programs=dhw_programs,
    )
    assert state == {
        "Parameter": "561",
        "Value": "13:00-14:00 ##:##-##:## ##:##-##:##",
        "Type": "1",
    }

    # Test preparing Tuesday time program
    dhw_programs = DHWTimeSwitchPrograms(tuesday="06:00-08:00 17:00-20:00 ##:##-##:##")
    state = mock_bsblan._prepare_hot_water_state(
        nominal_setpoint=None,
        reduced_setpoint=None,
        operating_mode=None,
        dhw_time_programs=dhw_programs,
    )
    assert state == {
        "Parameter": "562",
        "Value": "06:00-08:00 17:00-20:00 ##:##-##:##",
        "Type": "1",
    }

    # Test preparing standard values
    dhw_programs = DHWTimeSwitchPrograms(standard_values="0")
    state = mock_bsblan._prepare_hot_water_state(
        nominal_setpoint=None,
        reduced_setpoint=None,
        operating_mode=None,
        dhw_time_programs=dhw_programs,
    )
    assert state == {
        "Parameter": "576",
        "Value": "0",
        "Type": "1",
    }
