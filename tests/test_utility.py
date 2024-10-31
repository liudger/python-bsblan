"""Test cases for utility module."""

# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

from __future__ import annotations

import logging
from typing import Any

import pytest

from bsblan.utility import APIValidator


@pytest.fixture
def mock_request_data() -> dict[str, Any]:
    """Fixture for mock request data."""
    return {
        "700": {
            "name": "Operating mode",
            "error": 0,
            "value": "3",
            "desc": "Comfort",
            "dataType": 1,
            "readonly": 0,
            "unit": "",
        },
        "710": {
            "name": "Comfort setpoint",
            "error": 0,
            "value": "20.0",
            "desc": "",
            "dataType": 0,
            "readonly": 0,
            "unit": "°C",
        },
    }


@pytest.fixture
def validator() -> APIValidator:
    """Fixture for APIValidator instance."""
    api_config = {
        "heating": {
            "700": "hvac_mode",
            "710": "target_temperature",
            # Add other parameters as needed
        },
        "staticValues": {
            "714": "min_temp",
            "716": "max_temp",
            # Add other parameters as needed
        },
        "hot_water": {
            "8830": "dhw_actual_value_top_temperature",
            "8820": "state_dhw_pump",
            # Add other parameters as needed
        },
    }
    validated_sections: set[str] = set()
    return APIValidator(api_config=api_config, validated_sections=validated_sections)


def test_is_valid_param(validator: APIValidator) -> None:
    """Test parameter validation logic."""
    valid_param: dict[str, Any] = {
        "value": "20.0",
    }
    assert validator._is_valid_param(valid_param) is True

    invalid_params: list[dict[str, Any]] = [
        {"value": None},  # None value
        {"value": "---"},  # Invalid value
        {},  # Empty dict
    ]

    for param in invalid_params:
        assert validator._is_valid_param(param) is False


def test_get_section_params(validator: APIValidator) -> None:
    """Test getting section parameters."""
    # Test existing section
    heating_params = validator.get_section_params("heating")
    assert isinstance(heating_params, dict)
    assert "700" in heating_params
    assert heating_params["700"] == "hvac_mode"

    # Test non-existent section
    empty_params = validator.get_section_params("non_existent")
    assert isinstance(empty_params, dict)
    assert len(empty_params) == 0


def test_is_section_validated(validator: APIValidator) -> None:
    """Test section validation status checking."""
    assert validator.is_section_validated("heating") is False

    validator.validated_sections.add("heating")
    assert validator.is_section_validated("heating") is True


def test_reset_validation(validator: APIValidator) -> None:
    """Test validation reset functionality."""
    # Add some validated sections
    validator.validated_sections.update({"heating", "sensor"})
    validator.reset_validation()
    assert len(validator.validated_sections) == 0


def test_api_validator_with_empty_sections() -> None:
    """Test APIValidator with empty API config sections."""
    empty_config: dict[str, dict[str, Any]] = {
        "heating": {},
        "sensor": {},
        "device": {},
        "staticValues": {},
        "hot_water": {},
    }
    validator = APIValidator(empty_config)

    assert validator.get_section_params("heating") == {}
    assert not validator.is_section_validated("heating")


def test_api_validator_error_handling(
    validator: APIValidator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling in APIValidator."""
    with caplog.at_level(logging.INFO):
        # Test with invalid request data
        validator.validate_section("heating", {})
        assert "Parameter" in caplog.text


def test_api_validator_logging(
    validator: APIValidator,
    mock_request_data: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logging functionality in APIValidator."""
    with caplog.at_level(logging.DEBUG):
        validator.validate_section("heating", mock_request_data)

    # Verify debug logs
    assert "Validated section 'heating'" in caplog.text
    assert "removed" in caplog.text


def test_api_validator_concurrent_validation(
    validator: APIValidator,
    mock_request_data: dict[str, Any],
) -> None:
    """Test concurrent validation of multiple sections."""
    # Simulate concurrent validation attempts
    validator.validate_section("heating", mock_request_data)
    validator.validate_section("heating", mock_request_data)

    assert len(validator.validated_sections) == 1
    assert "heating" in validator.validated_sections
