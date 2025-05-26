"""Tests for EntityInfo value conversion error handling."""

import logging
from datetime import time

import pytest

from bsblan.models import DataType, EntityInfo


def test_entity_info_invalid_time_conversion() -> None:
    """Test EntityInfo with invalid time format."""
    # Create EntityInfo with invalid time format
    entity = EntityInfo(
        name="Invalid Time",
        value="24:61",  # Invalid time
        unit="",
        desc="",
        data_type=DataType.TIME,
    )

    # The value should remain as string since conversion failed
    assert entity.value == "24:61"


def test_entity_info_invalid_weekday_conversion() -> None:
    """Test EntityInfo with invalid weekday format."""
    # Create EntityInfo with invalid weekday format
    entity = EntityInfo(
        name="Invalid Weekday",
        value="not-a-number",  # Invalid weekday
        unit="",
        desc="",
        data_type=DataType.WEEKDAY,
    )

    # The value should remain as string since conversion failed
    assert entity.value == "not-a-number"


def test_entity_info_general_conversion_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test EntityInfo with general conversion error."""
    with caplog.at_level(logging.WARNING):
        # Create EntityInfo that will cause a conversion error
        entity = EntityInfo(
            name="Error Test",
            value=object(),  # Object that can't be converted
            unit="",
            desc="",
            data_type=DataType.PLAIN_NUMBER,
        )

        # The original value should be preserved
        assert isinstance(entity.value, object)
        assert "Failed to convert value" in caplog.text


def test_entity_info_valid_time_conversion() -> None:
    """Test EntityInfo with valid time format."""
    # Create EntityInfo with valid time format
    entity = EntityInfo(
        name="Valid Time",
        value="14:30",
        unit="",
        desc="",
        data_type=DataType.TIME,
    )

    # The value should be converted to a time object
    assert isinstance(entity.value, time)
    assert entity.value.hour == 14
    assert entity.value.minute == 30


def test_entity_info_enum_description() -> None:
    """Test the enum_description property."""
    # Create EntityInfo with ENUM data type
    enum_entity = EntityInfo(
        name="Test Enum",
        value="1",
        unit="",
        desc="Enum Description",
        data_type=DataType.ENUM,
    )

    # The enum_description should return the desc field
    assert enum_entity.enum_description == "Enum Description"

    # Create EntityInfo with non-ENUM data type
    non_enum_entity = EntityInfo(
        name="Test Value",
        value="22",
        unit="°C",
        desc="Not an Enum",
        data_type=DataType.PLAIN_NUMBER,
    )

    # The enum_description should return None
    assert non_enum_entity.enum_description is None
