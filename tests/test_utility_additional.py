"""Additional tests for the utility module."""

# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

from __future__ import annotations

import logging
from typing import Any

import pytest

from bsblan.utility import APIValidator


@pytest.fixture
def mock_request_data_invalid() -> dict[str, Any]:
    """Fixture for invalid mock request data."""
    return {
        "700": {
            "name": "Operating mode heating circuit 1",
            "value": "---",  # Invalid value
            "unit": "",
            "desc": "",
        },
        "710": {
            "name": "Comfort setpoint heating circuit 1",
            # Missing value field
            "unit": "°C",
            "desc": "",
        },
    }


@pytest.fixture
def fresh_api_validator() -> APIValidator:
    """Fixture for a fresh APIValidator instance with empty validated_sections."""
    api_config = {
        "heating": {
            "700": "hvac_mode",
            "710": "target_temperature",
        },
        "staticValues": {
            "714": "min_temp",
            "716": "max_temp",
        },
        "hot_water": {
            "8830": "dhw_actual_value_top_temperature",
            "8820": "state_dhw_pump",
        },
    }
    validated_sections: set[str] = set()
    return APIValidator(api_config=api_config, validated_sections=validated_sections)


def test_validate_section_with_invalid_values(
    fresh_api_validator: APIValidator,
    mock_request_data_invalid: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating a section with invalid data values."""
    with caplog.at_level(logging.INFO):
        # The validation will run but log errors for invalid data
        fresh_api_validator.validate_section("heating", mock_request_data_invalid)

        # Check that appropriate error messages were logged
        assert "returned invalid value" in caplog.text


def test_api_validator_with_non_existing_section(
    fresh_api_validator: APIValidator,
) -> None:
    """Test APIValidator with a non-existing section."""
    # Test with a section that doesn't exist in the api_config
    non_existent_section_params = fresh_api_validator.get_section_params(
        "non_existent_section"
    )
    assert non_existent_section_params == {}

    # Check that the non-existent section is not validated
    assert not fresh_api_validator.is_section_validated("non_existent_section")


def test_api_validator_with_empty_request_logs(
    fresh_api_validator: APIValidator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that APIValidator logs appropriate messages with empty request data."""
    # Test with empty request data
    caplog.clear()
    with caplog.at_level(logging.INFO):
        fresh_api_validator.validate_section("heating", {})

        # Check that appropriate warning messages were logged
        assert "Parameter" in caplog.text
        assert "not found in device response" in caplog.text
