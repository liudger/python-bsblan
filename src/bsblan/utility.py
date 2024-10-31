"""Utility functions for BSB-LAN integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from constants import APIConfig

logger = logging.getLogger(__name__)


@dataclass
class APIValidator:
    """Validates and maintains BSB-LAN API configuration."""

    api_config: APIConfig
    validated_sections: set[str] = field(default_factory=set)

    def validate_section(self, section: str, request_data: dict[str, Any]) -> None:
        """Validate and update a section of API config based on actual device support.

        Args:
            section: The section of the API config to validate
                (e.g., 'heating', 'hot_water')
            request_data: Response data from the device for validation

        """
        # Check if the section exists in the APIConfig object
        section_config = getattr(self.api_config, section, None)
        if section not in self.api_config:
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
        return self.api_config.get(section, {}).copy()

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
