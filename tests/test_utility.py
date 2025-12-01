"""Test cases for utility module."""

# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

from __future__ import annotations

import logging
from typing import Any

import pytest

from bsblan.utility import APIValidator, validate_time_format


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


# =============================================================================
# Tests for validate_time_format utility function
# =============================================================================


class TestValidateTimeFormat:
    """Test cases for validate_time_format utility function."""

    # Default year range for most tests
    MIN_YEAR = 1900
    MAX_YEAR = 2100

    def test_valid_time_format_basic(self) -> None:
        """Test that valid time formats are accepted."""
        valid_formats = [
            "01.01.2024 00:00:00",  # New Year midnight
            "31.12.2024 23:59:59",  # New Year's Eve end of day
            "15.06.2025 12:30:45",  # Mid-year, midday
            "13.08.2025 10:25:55",  # Example from BSB-LAN docs
        ]
        for time_value in valid_formats:
            # Should not raise any exception
            validate_time_format(time_value, self.MIN_YEAR, self.MAX_YEAR)

    def test_valid_time_format_boundary_days(self) -> None:
        """Test valid boundary days for each month."""
        valid_formats = [
            "31.01.2024 12:00:00",  # January 31
            "28.02.2023 12:00:00",  # February 28 (non-leap year)
            "31.03.2024 12:00:00",  # March 31
            "30.04.2024 12:00:00",  # April 30
            "31.05.2024 12:00:00",  # May 31
            "30.06.2024 12:00:00",  # June 30
            "31.07.2024 12:00:00",  # July 31
            "31.08.2024 12:00:00",  # August 31
            "30.09.2024 12:00:00",  # September 30
            "31.10.2024 12:00:00",  # October 31
            "30.11.2024 12:00:00",  # November 30
            "31.12.2024 12:00:00",  # December 31
        ]
        for time_value in valid_formats:
            validate_time_format(time_value, self.MIN_YEAR, self.MAX_YEAR)

    def test_invalid_format_wrong_separators(self) -> None:
        """Test that wrong date/time separators are rejected."""
        invalid_formats = [
            "2024-01-01 12:30:45",  # ISO format (wrong date separator)
            "01/01/2024 12:30:45",  # Slash separator
            "01-01-2024 12:30:45",  # Dash separator
            "01.01.2024-12:30:45",  # Wrong datetime separator
            "01.01.2024T12:30:45",  # ISO T separator
            "01.01.2024 12.30.45",  # Dots in time
        ]
        for time_value in invalid_formats:
            with pytest.raises(ValueError, match="Invalid time format"):
                validate_time_format(time_value, self.MIN_YEAR, self.MAX_YEAR)

    def test_invalid_format_wrong_digit_count(self) -> None:
        """Test that wrong digit counts are rejected."""
        invalid_formats = [
            "1.01.2024 12:30:45",  # Single digit day
            "01.1.2024 12:30:45",  # Single digit month
            "01.01.24 12:30:45",  # Two digit year
            "01.01.2024 1:30:45",  # Single digit hour
            "01.01.2024 12:3:45",  # Single digit minute
            "01.01.2024 12:30:4",  # Single digit second
        ]
        for time_value in invalid_formats:
            with pytest.raises(ValueError, match="Invalid time format"):
                validate_time_format(time_value, self.MIN_YEAR, self.MAX_YEAR)

    def test_invalid_format_missing_parts(self) -> None:
        """Test that incomplete formats are rejected."""
        invalid_formats = [
            "01.01.2024",  # Missing time
            "12:30:45",  # Missing date
            "01.01.2024 12:30",  # Missing seconds
            "01.2024 12:30:45",  # Missing day
            "",  # Empty string
            "invalid format",  # Completely wrong
        ]
        for time_value in invalid_formats:
            with pytest.raises(ValueError, match="Invalid time format"):
                validate_time_format(time_value, self.MIN_YEAR, self.MAX_YEAR)

    def test_invalid_day_out_of_range(self) -> None:
        """Test that out-of-range days are rejected."""
        with pytest.raises(ValueError, match="Invalid day: 0"):
            validate_time_format("00.01.2024 12:30:45", self.MIN_YEAR, self.MAX_YEAR)

        with pytest.raises(ValueError, match="Invalid day: 32"):
            validate_time_format("32.01.2024 12:30:45", self.MIN_YEAR, self.MAX_YEAR)

    def test_invalid_month_out_of_range(self) -> None:
        """Test that out-of-range months are rejected."""
        with pytest.raises(ValueError, match="Invalid month: 0"):
            validate_time_format("01.00.2024 12:30:45", self.MIN_YEAR, self.MAX_YEAR)

        with pytest.raises(ValueError, match="Invalid month: 13"):
            validate_time_format("01.13.2024 12:30:45", self.MIN_YEAR, self.MAX_YEAR)

    def test_invalid_hour_out_of_range(self) -> None:
        """Test that out-of-range hours are rejected."""
        with pytest.raises(ValueError, match="Invalid hour: 24"):
            validate_time_format("01.01.2024 24:30:45", self.MIN_YEAR, self.MAX_YEAR)

        with pytest.raises(ValueError, match="Invalid hour: 25"):
            validate_time_format("01.01.2024 25:30:45", self.MIN_YEAR, self.MAX_YEAR)

    def test_invalid_minute_out_of_range(self) -> None:
        """Test that out-of-range minutes are rejected."""
        with pytest.raises(ValueError, match="Invalid minute: 60"):
            validate_time_format("01.01.2024 12:60:45", self.MIN_YEAR, self.MAX_YEAR)

        with pytest.raises(ValueError, match="Invalid minute: 65"):
            validate_time_format("01.01.2024 12:65:45", self.MIN_YEAR, self.MAX_YEAR)

    def test_invalid_second_out_of_range(self) -> None:
        """Test that out-of-range seconds are rejected."""
        with pytest.raises(ValueError, match="Invalid second: 60"):
            validate_time_format("01.01.2024 12:30:60", self.MIN_YEAR, self.MAX_YEAR)

        with pytest.raises(ValueError, match="Invalid second: 65"):
            validate_time_format("01.01.2024 12:30:65", self.MIN_YEAR, self.MAX_YEAR)

    def test_invalid_day_for_30_day_months(self) -> None:
        """Test that day 31 is rejected for 30-day months."""
        thirty_day_months = [4, 6, 9, 11]  # April, June, September, November
        for month in thirty_day_months:
            time_value = f"31.{month:02d}.2024 12:30:45"
            with pytest.raises(ValueError, match=f"Invalid day 31 for month {month}"):
                validate_time_format(time_value, self.MIN_YEAR, self.MAX_YEAR)

    # -------------------------------------------------------------------------
    # Leap year edge cases
    # -------------------------------------------------------------------------

    def test_leap_year_february_29_valid(self) -> None:
        """Test that February 29 is valid in leap years."""
        leap_years = [
            2024,  # Divisible by 4
            2000,  # Divisible by 400 (century leap year)
            2400,  # Divisible by 400
        ]
        for year in leap_years:
            time_value = f"29.02.{year} 12:30:45"
            # Should not raise - these are valid leap years
            validate_time_format(time_value, 1900, 2500)

    def test_non_leap_year_february_29_invalid(self) -> None:
        """Test that February 29 is invalid in non-leap years."""
        non_leap_years = [
            2023,  # Not divisible by 4
            2025,  # Not divisible by 4
            1900,  # Divisible by 100 but not 400 (not a leap year)
            2100,  # Divisible by 100 but not 400 (not a leap year)
        ]
        for year in non_leap_years:
            time_value = f"29.02.{year} 12:30:45"
            with pytest.raises(
                ValueError,
                match=f"Invalid day 29 for February in year {year}",
            ):
                validate_time_format(time_value, 1900, 2500)

    def test_leap_year_february_28_always_valid(self) -> None:
        """Test that February 28 is valid in any year."""
        years = [2023, 2024, 1900, 2000, 2100]
        for year in years:
            time_value = f"28.02.{year} 12:30:45"
            validate_time_format(time_value, 1900, 2500)

    def test_leap_year_february_30_always_invalid(self) -> None:
        """Test that February 30 is always invalid, even in leap years."""
        for year in [2024, 2000]:  # Leap years
            time_value = f"30.02.{year} 12:30:45"
            with pytest.raises(
                ValueError,
                match=f"Invalid day 30 for February in year {year}",
            ):
                validate_time_format(time_value, 1900, 2500)

    # -------------------------------------------------------------------------
    # Year range boundary conditions
    # -------------------------------------------------------------------------

    def test_year_at_minimum_boundary(self) -> None:
        """Test that the minimum year boundary is inclusive."""
        # Exactly at minimum should be valid
        validate_time_format("01.01.1900 12:30:45", 1900, 2100)

        # One below minimum should be invalid
        with pytest.raises(ValueError, match="Invalid year: 1899"):
            validate_time_format("01.01.1899 12:30:45", 1900, 2100)

    def test_year_at_maximum_boundary(self) -> None:
        """Test that the maximum year boundary is inclusive."""
        # Exactly at maximum should be valid
        validate_time_format("01.01.2100 12:30:45", 1900, 2100)

        # One above maximum should be invalid
        with pytest.raises(ValueError, match="Invalid year: 2101"):
            validate_time_format("01.01.2101 12:30:45", 1900, 2100)

    def test_custom_year_range(self) -> None:
        """Test that custom year ranges are respected."""
        # Test with a narrow range
        validate_time_format("01.01.2020 12:30:45", 2020, 2025)
        validate_time_format("01.01.2025 12:30:45", 2020, 2025)

        with pytest.raises(ValueError, match="Invalid year: 2019"):
            validate_time_format("01.01.2019 12:30:45", 2020, 2025)

        with pytest.raises(ValueError, match="Invalid year: 2026"):
            validate_time_format("01.01.2026 12:30:45", 2020, 2025)

    def test_time_boundary_values(self) -> None:
        """Test time boundary values (00:00:00 and 23:59:59)."""
        # Minimum time
        validate_time_format("01.01.2024 00:00:00", self.MIN_YEAR, self.MAX_YEAR)

        # Maximum time
        validate_time_format("01.01.2024 23:59:59", self.MIN_YEAR, self.MAX_YEAR)
