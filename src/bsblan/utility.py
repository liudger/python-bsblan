"""Utility functions for BSB-LAN integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .constants import CircuitConfig

logger = logging.getLogger(__name__)


def is_param_value_active(param: dict[str, Any] | None) -> bool:
    """Check whether a parameter payload carries an active value.

    Args:
        param: The parameter payload returned by the device.

    Returns:
        bool: True if the payload is non-empty and its value is neither
            None nor the inactive marker ("---").

    """
    if not param:
        return False
    return param.get("value") not in (None, CircuitConfig.INACTIVE_MARKER)


@dataclass
class APIValidator:
    """Validates and maintains BSB-LAN API configuration."""

    # Flexible type for API data (accepts `APIConfig`, plain dicts, or None)
    api_config: Any  # intentionally permissive to support tests and dynamic data
    validated_sections: set[str] = field(default_factory=set)
    validated_parameters: dict[str, set[str]] = field(default_factory=dict)

    def validate_section(
        self,
        section: str,
        request_data: dict[str, Any],
        include: list[str] | None = None,
        parameter_ids: set[str] | None = None,
    ) -> None:
        """Validate and update a section of API config based on actual device support.

        Args:
            section: The section of the API config to validate
                (e.g., 'heating', 'hot_water')
            request_data: Response data from the device for validation
            include: Optional list of parameter names to validate. If None,
                validates all parameters for the section.
            parameter_ids: Optional parameter IDs to validate. When supplied,
                takes precedence over ``include``.

        """
        # Check if the section exists in the APIConfig object
        if not self.api_config or section not in self.api_config:
            logger.warning("Unknown section '%s' in API configuration", section)
            return

        if section in self.validated_sections:
            logger.debug("Section '%s' was already validated", section)
            return

        section_config = self.api_config[section]
        params_to_remove = []
        validated_ids = set()

        # Check each parameter in the section (filtered by include if specified)
        for param_id, param_name in list(section_config.items()):
            # Skip params not in include list (if include is specified)
            if parameter_ids is not None and param_id not in parameter_ids:
                continue
            if (
                parameter_ids is None
                and include is not None
                and param_name not in include
            ):
                continue

            validated_ids.add(param_id)

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

        self.validated_parameters.setdefault(section, set()).update(validated_ids)
        if set(section_config).issubset(self.validated_parameters[section]):
            self.validated_sections.add(section)
        else:
            self.validated_sections.discard(section)

        logger.debug(
            "Validated section '%s': removed %d unsupported parameters",
            section,
            len(params_to_remove),
        )

    def _is_valid_param(self, param: dict[str, Any]) -> bool:
        """Check if parameter data is valid."""
        return is_param_value_active(param)

    def get_section_params(self, section: str) -> Any:
        """Get the parameter mapping for a section."""
        return (self.api_config or {}).get(section, {}).copy()

    def are_parameters_validated(self, section: str, parameter_ids: set[str]) -> bool:
        """Check whether every requested parameter ID was validated."""
        return section in self.validated_sections or parameter_ids.issubset(
            self.validated_parameters.get(section, set())
        )

    def is_section_validated(self, section: str) -> bool:
        """Check whether every current parameter in a section was validated."""
        return section in self.validated_sections

    def reset_validation(self, section: str | None = None) -> None:
        """Reset validation state for a section or all sections.

        Args:
            section: Specific section to reset, or None to reset all

        """
        if section is None:
            self.validated_sections.clear()
            self.validated_parameters.clear()
        elif section in self.validated_sections:
            self.validated_sections.remove(section)
            self.validated_parameters.pop(section, None)
        else:
            self.validated_parameters.pop(section, None)
