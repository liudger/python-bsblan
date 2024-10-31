"""Tests for utility functions and classes."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from bsblan.constants import API_V3
from bsblan.utility import APIValidator

# Setup logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


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
def api_validator() -> APIValidator:
    """Fixture for APIValidator instance."""
    return APIValidator(API_V3)


def test_api_validator_initialization(api_validator: APIValidator) -> None:
    """Test APIValidator initialization."""
    assert api_validator.api_config == API_V3
    assert isinstance(api_validator.validated_sections, set)
    assert len(api_validator.validated_sections) == 0


def test_validate_section_success(
    api_validator: APIValidator,
    mock_request_data: dict[str, Any],
) -> None:
    """Test successful section validation."""
    api_validator.validate_section("heating", mock_request_data)
    assert "heating" in api_validator.validated_sections


def test_validate_section_unknown(
    api_validator: APIValidator,
    mock_request_data: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validation of unknown section."""
    with caplog.at_level(logging.WARNING):
        api_validator.validate_section("unknown_section", mock_request_data)
    assert "unknown_section" not in api_validator.validated_sections
    assert "Unknown section 'unknown_section' in API configuration" in caplog.text


def test_validate_section_already_validated(
    api_validator: APIValidator,
    mock_request_data: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validation of already validated section."""
    api_validator.validated_sections.add("heating")
    with caplog.at_level(logging.DEBUG):
        api_validator.validate_section("heating", mock_request_data)
    assert "Section 'heating' was already validated" in caplog.text


def test_validate_section_missing_parameter(
    api_validator: APIValidator,
    mock_request_data: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validation with missing parameter."""
    # Remove a parameter that should be present
    mock_request_data.pop("700")

    with caplog.at_level(logging.INFO):
        api_validator.validate_section("heating", mock_request_data)

    assert "Parameter 700 (hvac_mode) not found in device response" in caplog.text


# def test_validate_section_invalid_parameter(
#     api_validator: APIValidator,
#     mock_request_data: dict[str, Any],
#     caplog: pytest.LogCaptureFixture,
# ) -> None:
#     """Test validation with invalid parameter value."""
#     mock_request_data["700"]["---"] = 1  # Set --- to make parameter invalid

#     with caplog.at_level(logging.INFO):
#         api_validator.validate_section("heating", mock_request_data)

#     # Debugging: Print captured logs to see what's actually logged
#     print("Captured Logs:", caplog.text)

#     assert "Parameter 700 (hvac_mode) returned invalid value: ---" in caplog.text


def test_is_valid_param(api_validator: APIValidator) -> None:
    """Test parameter validation logic."""
    valid_param = {
        "value": "20.0",
    }
    assert api_validator._is_valid_param(valid_param) is True

    invalid_params = [
        {"value": None},  # None value
        {"value": "---"},  # Invalid value
        {},  # Empty dict
    ]

    for param in invalid_params:
        assert api_validator._is_valid_param(param) is False


def test_get_section_params(api_validator: APIValidator) -> None:
    """Test getting section parameters."""
    # Test existing section
    heating_params = api_validator.get_section_params("heating")
    assert isinstance(heating_params, dict)
    assert "710" in heating_params
    assert heating_params["710"] == "target_temperature"

    # Test non-existent section
    empty_params = api_validator.get_section_params("non_existent")
    assert isinstance(empty_params, dict)
    assert len(empty_params) == 0


def test_is_section_validated(api_validator: APIValidator) -> None:
    """Test section validation status checking."""
    assert api_validator.is_section_validated("heating") is False

    api_validator.validated_sections.add("heating")
    assert api_validator.is_section_validated("heating") is True


def test_reset_validation(api_validator: APIValidator) -> None:
    """Test validation reset functionality."""
    # Add some validated sections
    api_validator.validated_sections.update({"heating", "sensor"})

    # Test resetting specific section
    api_validator.reset_validation("heating")
    assert "heating" not in api_validator.validated_sections
    assert "sensor" in api_validator.validated_sections

    # Test resetting all sections
    api_validator.reset_validation()
    assert len(api_validator.validated_sections) == 0


def test_validate_section_parameter_removal(
    api_validator: APIValidator,
    mock_request_data: dict[str, Any],
) -> None:
    """Test removal of invalid parameters during validation."""
    # Add an invalid parameter to the mock data
    mock_request_data["700"]["value"] = "---"

    api_validator.validate_section("heating", mock_request_data)

    # Get the validated parameters
    validated_params = api_validator.get_section_params("heating")
    assert "700" not in validated_params  # Should be removed due to invalid value


def test_validate_multiple_sections(
    api_validator: APIValidator,
    mock_request_data: dict[str, Any],
) -> None:
    """Test validation of multiple sections."""
    # Validate heating section
    api_validator.validate_section("heating", mock_request_data)
    assert "heating" in api_validator.validated_sections

    # Validate sensor section with different data
    sensor_data = {
        "8700": {"name": "Outside temp", "error": 0, "value": "15.5", "unit": "°C"},
        "8740": {"name": "Room temp", "error": 0, "value": "21.0", "unit": "°C"},
    }
    api_validator.validate_section("sensor", sensor_data)
    assert "sensor" in api_validator.validated_sections

    # Verify both sections maintain their validation
    assert len(api_validator.validated_sections) == 2


def test_api_validator_error_handling(
    api_validator: APIValidator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling in APIValidator."""
    with caplog.at_level(logging.INFO):
        # Test with invalid request data
        api_validator.validate_section("heating", {})
        assert "Parameter" in caplog.text

def test_api_validator_logging(
    api_validator: APIValidator,
    mock_request_data: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logging functionality in APIValidator."""
    with caplog.at_level(logging.DEBUG):
        api_validator.validate_section("heating", mock_request_data)

    # Verify debug logs
    assert "Validated section 'heating'" in caplog.text
    assert "removed" in caplog.text


def test_api_validator_with_empty_sections() -> None:
    """Test APIValidator with empty API config sections."""
    empty_config = {
        "heating": {},
        "sensor": {},
        "device": {},
        "staticValues": {},
        "hot_water": {},
    }
    validator = APIValidator(empty_config)  # type: ignore[arg-type]

    assert validator.get_section_params("heating") == {}
    assert not validator.is_section_validated("heating")


def test_api_validator_concurrent_validation(
    api_validator: APIValidator,
    mock_request_data: dict[str, Any],
) -> None:
    """Test concurrent validation of multiple sections."""
    # Simulate concurrent validation attempts
    api_validator.validate_section("heating", mock_request_data)
    api_validator.validate_section("heating", mock_request_data)

    assert len(api_validator.validated_sections) == 1
    assert "heating" in api_validator.validated_sections
