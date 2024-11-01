"""Tests for setting BSBLAN hot water state."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

from unittest.mock import AsyncMock

import pytest

from bsblan import BSBLAN, BSBLANError
from bsblan.constants import MULTI_PARAMETER_ERROR_MSG, NO_STATE_ERROR_MSG


@pytest.mark.asyncio
async def test_set_hot_water(mock_bsblan: BSBLAN) -> None:
    """Test setting BSBLAN hot water state.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test setting nominal_setpoint
    assert isinstance(mock_bsblan._request, AsyncMock)
    await mock_bsblan.set_hot_water(nominal_setpoint=60.0)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={
            "Parameter": "1610",
            "Value": "60.0",
            "Type": "1",
        },
    )

    # Test setting reduced_setpoint
    await mock_bsblan.set_hot_water(reduced_setpoint=40.0)
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
        await mock_bsblan.set_hot_water(nominal_setpoint=60.0, reduced_setpoint=40.0)


@pytest.mark.asyncio
async def test_prepare_hot_water_state(mock_bsblan: BSBLAN) -> None:
    """Test preparing hot water state.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    # Test preparing nominal_setpoint
    state = mock_bsblan._prepare_hot_water_state(
        nominal_setpoint=60.0,
        reduced_setpoint=None,
        operating_mode=None,
    )
    assert state == {
        "Parameter": "1610",
        "Value": "60.0",
        "Type": "1",
    }

    # Test preparing reduced_setpoint
    state = mock_bsblan._prepare_hot_water_state(
        nominal_setpoint=None,
        reduced_setpoint=40.0,
        operating_mode=None,
    )
    assert state == {
        "Parameter": "1612",
        "Value": "40.0",
        "Type": "1",
    }

    # Test preparing no parameters (should raise an error)
    with pytest.raises(BSBLANError, match=NO_STATE_ERROR_MSG):
        mock_bsblan._prepare_hot_water_state(
            nominal_setpoint=None,
            reduced_setpoint=None,
            operating_mode=None,
        )

    # test preparing operating_mode
    state = mock_bsblan._prepare_hot_water_state(
        nominal_setpoint=None,
        reduced_setpoint=None,
        operating_mode="3",
    )

    assert state == {
        "Parameter": "1600",
        "EnumValue": "3",
        "Type": "1",
    }


@pytest.mark.asyncio
async def test_set_hot_water_state(
    mock_bsblan: BSBLAN,
) -> None:
    """Test setting hot water state.

    Args:
        mock_bsblan (BSBLAN): The mock BSBLAN instance.

    """
    state = {
        "Parameter": "1600",
        "EnumValue": "3",
        "Type": "1",
    }
    await mock_bsblan._set_hot_water_state(state)
    assert isinstance(mock_bsblan._request, AsyncMock)  # Type check
    mock_bsblan._request.assert_awaited_with(base_path="/JS", data=state)
