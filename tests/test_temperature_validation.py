"""Tests for temperature validation error handling."""
# pylint: disable=protected-access

import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import TEMPERATURE_RANGE_ERROR_MSG
from bsblan.exceptions import BSBLANError, BSBLANInvalidParameterError


def test_validate_target_temperature_no_range() -> None:
    """Test validating target temperature with temperature range not initialized."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Temperature range is not initialized by default
    with pytest.raises(BSBLANError, match=TEMPERATURE_RANGE_ERROR_MSG):
        bsblan._validate_target_temperature("22.0")


def test_validate_target_temperature_invalid_value() -> None:
    """Test validating target temperature with invalid (non-numeric) value."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Initialize temperature range
    bsblan._min_temp = 10.0
    bsblan._max_temp = 30.0

    # Test with non-numeric value
    with pytest.raises(BSBLANInvalidParameterError):
        bsblan._validate_target_temperature("invalid")


def test_validate_target_temperature_out_of_range() -> None:
    """Test validating target temperature with value outside allowed range."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Initialize temperature range
    bsblan._min_temp = 10.0
    bsblan._max_temp = 30.0

    # Test with value below minimum
    with pytest.raises(BSBLANInvalidParameterError):
        bsblan._validate_target_temperature("5.0")

    # Test with value above maximum
    with pytest.raises(BSBLANInvalidParameterError):
        bsblan._validate_target_temperature("35.0")


def test_validate_target_temperature_valid() -> None:
    """Test validating target temperature with valid value."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Initialize temperature range
    bsblan._min_temp = 10.0
    bsblan._max_temp = 30.0

    # Test with valid value (should not raise exception)
    bsblan._validate_target_temperature("22.0")
