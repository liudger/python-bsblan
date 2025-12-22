"""Utility functions for BSB-LAN integration."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


def validate_time_format(
    time_value: str,
    min_year: int,
    max_year: int,
) -> None:
    """Validate the BSB-LAN time format.

    Args:
        time_value: The time value to validate in format DD.MM.YYYY HH:MM:SS.
        min_year: Minimum valid year.
        max_year: Maximum valid year.

    Raises:
        ValueError: If the time format is invalid.

    """
    # BSB-LAN supports format: DD.MM.YYYY HH:MM:SS (e.g., "13.08.2025 10:25:55")
    pattern = r"^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})$"

    match = re.match(pattern, time_value)
    if not match:
        msg = f"Invalid time format: {time_value}. Expected DD.MM.YYYY HH:MM:SS"
        raise ValueError(msg)

    day, month, year, hour, minute, second = map(int, match.groups())

    # Validate ranges
    if not (1 <= day <= 31):
        msg = f"Invalid day: {day}"
        raise ValueError(msg)
    if not (1 <= month <= 12):
        msg = f"Invalid month: {month}"
        raise ValueError(msg)
    if not (min_year <= year <= max_year):
        msg = f"Invalid year: {year}"
        raise ValueError(msg)
    if not (0 <= hour <= 23):
        msg = f"Invalid hour: {hour}"
        raise ValueError(msg)
    if not (0 <= minute <= 59):
        msg = f"Invalid minute: {minute}"
        raise ValueError(msg)
    if not (0 <= second <= 59):
        msg = f"Invalid second: {second}"
        raise ValueError(msg)

    # Additional validation for days per month
    if month in (4, 6, 9, 11) and day > 30:
        msg = f"Invalid day {day} for month {month}"
        raise ValueError(msg)
    if month == 2:
        # Leap year check
        is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        max_day = 29 if is_leap else 28
        if day > max_day:
            msg = f"Invalid day {day} for February in year {year}"
            raise ValueError(msg)


@dataclass
class APIValidator:
    """Validates and maintains BSB-LAN API configuration."""

    # Flexible type for API data (accepts `APIConfig`, plain dicts, or None)
    api_config: Any  # intentionally permissive to support tests and dynamic data
    validated_sections: set[str] = field(default_factory=set)

    def validate_section(self, section: str, request_data: dict[str, Any]) -> None:
        """Validate and update a section of API config based on actual device support.

        Args:
            section: The section of the API config to validate
                (e.g., 'heating', 'hot_water')
            request_data: Response data from the device for validation

        """
        # Check if the section exists in the APIConfig object
        if not self.api_config or section not in self.api_config:
            logger.warning("Unknown section '%s' in API configuration", section)
            return

        # Skip if section was already validated
        if section in self.validated_sections:
            logger.debug("Section '%s' was already validated", section)
            return

        section_config = self.api_config[section]
        params_to_remove = []

        # Check each parameter in the section
        for param_id, param_name in section_config.items():
            if param_id not in request_data:
                logger.info(
                    "Parameter %s (%s) not found in device response",
                    param_id,
                    param_name,
                )
                params_to_remove.append(param_id)
                continue

            param_data = request_data[param_id]
            if not self._is_valid_param(param_data):
                logger.info(
                    "Parameter %s (%s) returned invalid value: %s",
                    param_id,
                    param_name,
                    param_data.get("value"),
                )
                params_to_remove.append(param_id)

        # Remove unsupported parameters from the configuration
        for param_id in params_to_remove:
            section_config.pop(param_id)

        # Mark section as validated
        self.validated_sections.add(section)

        logger.debug(
            "Validated section '%s': removed %d unsupported parameters",
            section,
            len(params_to_remove),
        )

    def _is_valid_param(self, param: dict[str, Any]) -> bool:
        """Check if parameter data is valid."""
        return not (not param or param.get("value") in (None, "---"))

    def get_section_params(self, section: str) -> Any:
        """Get the parameter mapping for a section."""
        return (self.api_config or {}).get(section, {}).copy()

    def is_section_validated(self, section: str) -> bool:
        """Check if a section has been validated."""
        return section in self.validated_sections

    def reset_validation(self, section: str | None = None) -> None:
        """Reset validation state for a section or all sections.

        Args:
            section: Specific section to reset, or None to reset all

        """
        if section is None:
            self.validated_sections.clear()
        elif section in self.validated_sections:
            self.validated_sections.remove(section)
