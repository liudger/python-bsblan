"""Tests for setting BSBLAN hot water state."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from unittest.mock import AsyncMock

import pytest

from bsblan import BSBLAN, BSBLANError, SetHotWaterParam
from bsblan.constants import MULTI_PARAMETER_ERROR_MSG, NO_STATE_ERROR_MSG


@pytest.mark.asyncio
async def test_set_hot_water(mock_bsblan: BSBLAN) -> None:
    """Test setting BSBLAN hot water state.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test setting nominal_setpoint
    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_hot_water(SetHotWaterParam(nominal_setpoint=60.0))
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1610",
            "Value": "60.0",
            "Type": "1",
        },
    )

    # Test setting reduced_setpoint
    await mock_bsblan.set_hot_water(SetHotWaterParam(reduced_setpoint=40.0))
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1612",
            "Value": "40.0",
            "Type": "1",
        },
    )

    # Test setting multiple parameters (should raise an error)
    with pytest.raises(BSBLANError, match=MULTI_PARAMETER_ERROR_MSG):
        await mock_bsblan.set_hot_water(
            SetHotWaterParam(nominal_setpoint=60.0, reduced_setpoint=40.0)
        )

    # Test setting new parameters
    await mock_bsblan.set_hot_water(SetHotWaterParam(eco_mode_selection="1"))
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1601",
            "Value": "1",
            "Type": "1",
        },
    )

    await mock_bsblan.set_hot_water(SetHotWaterParam(dhw_charging_priority="1"))
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1630",
            "Value": "1",
            "Type": "1",
        },
    )

    await mock_bsblan.set_hot_water(
        SetHotWaterParam(legionella_function_dwelling_time=15)
    )
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1646",
            "Value": "15",
            "Type": "1",
        },
    )

    await mock_bsblan.set_hot_water(SetHotWaterParam(legionella_function_setpoint=60.0))
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1645",
            "Value": "60.0",
            "Type": "1",
        },
    )

    await mock_bsblan.set_hot_water(
        SetHotWaterParam(legionella_function_periodicity="7")
    )
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1641",
            "Value": "7",
            "Type": "1",
        },
    )

    await mock_bsblan.set_hot_water(SetHotWaterParam(legionella_function_time="12:00"))
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1644",
            "Value": "12:00",
            "Type": "1",
        },
    )

    await mock_bsblan.set_hot_water(SetHotWaterParam(legionella_function_day="6"))
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1642",
            "Value": "6",
            "Type": "1",
        },
    )

    await mock_bsblan.set_hot_water(SetHotWaterParam(nominal_setpoint_max=65.0))
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1614",
            "Value": "65.0",
            "Type": "1",
        },
    )

    await mock_bsblan.set_hot_water(SetHotWaterParam(operating_mode_changeover="1"))
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1680",
            "Value": "1",
            "Type": "1",
        },
    )


@pytest.mark.asyncio
async def test_prepare_hot_water_state(mock_bsblan: BSBLAN) -> None:
    """Test preparing hot water state.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test preparing nominal_setpoint
    params = SetHotWaterParam(nominal_setpoint=60.0)
    state = mock_bsblan._prepare_hot_water_state(params)
    assert state == {
        "Parameter": "1610",
        "Value": "60.0",
        "Type": "1",
    }

    # Test preparing reduced_setpoint
    params = SetHotWaterParam(reduced_setpoint=40.0)
    state = mock_bsblan._prepare_hot_water_state(params)
    assert state == {
        "Parameter": "1612",
        "Value": "40.0",
        "Type": "1",
    }

    # Test preparing no parameters (should raise an error)
    params = SetHotWaterParam()
    with pytest.raises(BSBLANError, match=NO_STATE_ERROR_MSG):
        mock_bsblan._prepare_hot_water_state(params)

    # Test preparing operating_mode
    params = SetHotWaterParam(operating_mode="3")
    state = mock_bsblan._prepare_hot_water_state(params)

    assert state == {
        "Parameter": "1600",
        "Value": "3",
        "Type": "1",
    }

    # Test preparing new parameters
    params = SetHotWaterParam(eco_mode_selection="1")
    state = mock_bsblan._prepare_hot_water_state(params)
    assert state == {
        "Parameter": "1601",
        "Value": "1",
        "Type": "1",
    }

    params = SetHotWaterParam(dhw_charging_priority="1")
    state = mock_bsblan._prepare_hot_water_state(params)
    assert state == {
        "Parameter": "1630",
        "Value": "1",
        "Type": "1",
    }

    params = SetHotWaterParam(legionella_function_dwelling_time=15.0)
    state = mock_bsblan._prepare_hot_water_state(params)
    assert state == {
        "Parameter": "1646",
        "Value": "15.0",
        "Type": "1",
    }

    params = SetHotWaterParam(legionella_function_setpoint=60.0)
    state = mock_bsblan._prepare_hot_water_state(params)
    assert state == {
        "Parameter": "1645",
        "Value": "60.0",
        "Type": "1",
    }


@pytest.mark.asyncio
async def test_set_device_state(
    mock_bsblan: BSBLAN,
) -> None:
    """Test setting device state via unified method.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    state = {
        "Parameter": "1600",
        "Value": "3",
        "Type": "1",
    }
    await mock_bsblan._set_device_state(state)
    assert isinstance(mock_bsblan._request, AsyncMock)  # Type check
    mock_bsblan._request.assert_awaited_with(base_path="/JS", data=state)
