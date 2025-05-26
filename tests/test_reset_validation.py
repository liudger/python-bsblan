"""Tests for APIValidator reset_validation method."""

from bsblan.utility import APIValidator


def test_reset_validation_specific_section() -> None:
    """Test resetting validation for a specific section."""
    # Create a test API config
    api_config = {
        "heating": {"param1": "value1"},
        "sensor": {"param2": "value2"},
    }

    # Initialize APIValidator with some validated sections
    validator = APIValidator(api_config)
    validator.validated_sections.update({"heating", "sensor"})

    # Verify initial state
    assert validator.is_section_validated("heating") is True
    assert validator.is_section_validated("sensor") is True

    # Reset validation for just the heating section
    validator.reset_validation("heating")

    # Verify only heating was reset
    assert validator.is_section_validated("heating") is False
    assert validator.is_section_validated("sensor") is True


def test_reset_validation_nonexistent_section() -> None:
    """Test resetting validation for a section that wasn't validated."""
    # Create a test API config
    api_config = {
        "heating": {"param1": "value1"},
        "sensor": {"param2": "value2"},
    }

    # Initialize APIValidator with some validated sections
    validator = APIValidator(api_config)
    validator.validated_sections.add("heating")

    # Verify initial state
    assert validator.is_section_validated("heating") is True
    assert validator.is_section_validated("nonexistent") is False

    # Reset validation for a nonexistent section (should not error)
    validator.reset_validation("nonexistent")

    # Verify state remains unchanged
    assert validator.is_section_validated("heating") is True
    assert validator.is_section_validated("nonexistent") is False
