"""Test utility module edge cases."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from bsblan.constants import API_V3
from bsblan.utility import APIValidator

if TYPE_CHECKING:
    import pytest


def test_validate_section_unknown_section(caplog: pytest.LogCaptureFixture) -> None:
    """Test validation of an unknown section logs warning and returns."""
    api_validator = APIValidator(API_V3)

    # Mock the api_config to not have the section we're testing
    api_validator.api_config = MagicMock()
    api_validator.api_config.__contains__ = MagicMock(return_value=False)

    with caplog.at_level(logging.WARNING):
        api_validator.validate_section("unknown_section", {})

    # Should log a warning
    assert "Unknown section 'unknown_section' in API configuration" in caplog.text

    # Section should not be added to validated_sections
    assert "unknown_section" not in api_validator.validated_sections


def test_validate_section_already_validated(caplog: pytest.LogCaptureFixture) -> None:
    """Test validation of an already validated section logs debug and returns."""
    api_validator = APIValidator(API_V3)

    # Add section to validated_sections first
    api_validator.validated_sections.add("hot_water")

    with caplog.at_level(logging.DEBUG):
        api_validator.validate_section("hot_water", {})

    # Should log a debug message
    assert "Section 'hot_water' was already validated" in caplog.text
