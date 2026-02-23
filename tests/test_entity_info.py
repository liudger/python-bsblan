"""Tests for EntityInfo value conversion error handling."""

import logging
from datetime import time

import pytest

from bsblan.models import DataType, EntityInfo


def test_entity_info_invalid_time_conversion(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test EntityInfo with invalid time format logs a warning."""
    with caplog.at_level(logging.WARNING):
        entity = EntityInfo(
            name="Invalid Time",
            value="24:61",  # Invalid time
            unit="",
            desc="",
            data_type=DataType.TIME,
        )

        # The value should remain as string since conversion failed
        assert entity.value == "24:61"
        assert "Failed to convert value" in caplog.text


def test_entity_info_undefined_value_becomes_none() -> None:
    """Test that '---' (sensor/parameter not in use) is converted to None."""
    entity = EntityInfo(
        name="Inactive Sensor",
        value="---",
        unit="°C",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.value is None


def test_entity_info_invalid_weekday_conversion(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test EntityInfo with invalid weekday format logs a warning."""
    with caplog.at_level(logging.WARNING):
        entity = EntityInfo(
            name="Invalid Weekday",
            value="not-a-number",  # Invalid weekday
            unit="",
            desc="",
            data_type=DataType.WEEKDAY,
        )

        # The value should remain as string since conversion failed
        assert entity.value == "not-a-number"
        assert "Failed to convert value" in caplog.text


def test_entity_info_invalid_plain_number_conversion(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test non-temperature PLAIN_NUMBER conversion failure logs a warning."""
    with caplog.at_level(logging.WARNING):
        entity = EntityInfo(
            name="Invalid Number",
            value="not-numeric",
            unit="%",
            desc="",
            data_type=DataType.PLAIN_NUMBER,
        )

        # The value should remain as string since conversion failed
        assert entity.value == "not-numeric"
        assert "Failed to convert value" in caplog.text


def test_entity_info_invalid_enum_conversion(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test ENUM conversion failure logs a warning."""
    with caplog.at_level(logging.WARNING):
        entity = EntityInfo(
            name="Invalid Enum",
            value="not-an-int",
            unit="",
            desc="Some description",
            data_type=DataType.ENUM,
        )

        # The value should remain as string since conversion failed
        assert entity.value == "not-an-int"
        assert "Failed to convert value" in caplog.text


def test_entity_info_general_conversion_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test EntityInfo with general conversion error."""
    with caplog.at_level(logging.WARNING):
        # Create EntityInfo that will cause a conversion error
        # Using a non-numeric string with temperature unit triggers float() ValueError
        entity = EntityInfo(
            name="Error Test",
            value="not-convertible",
            unit="°C",
            desc="",
            data_type=DataType.PLAIN_NUMBER,
        )

        # The original value should be preserved
        assert entity.value == "not-convertible"
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


def test_entity_info_string_with_embedded_unit_kwh() -> None:
    """Test STRING value with embedded kWh unit is extracted to int."""
    entity = EntityInfo(
        name="Energy brought in",
        value="7968 kWh",
        unit="",
        desc="",
        data_type=DataType.STRING,
    )

    assert entity.value == 7968
    assert entity.unit == "kWh"


def test_entity_info_string_with_embedded_unit_float() -> None:
    """Test STRING value with embedded unit and decimal is extracted to float."""
    entity = EntityInfo(
        name="Power value",
        value="3.5 kW",
        unit="",
        desc="",
        data_type=DataType.STRING,
    )

    assert entity.value == 3.5
    assert entity.unit == "kW"


def test_entity_info_string_with_unknown_unit_kept_as_string() -> None:
    """Test STRING value with unknown unit remains as string."""
    entity = EntityInfo(
        name="Unknown unit",
        value="42 foobar",
        unit="",
        desc="",
        data_type=DataType.STRING,
    )

    assert entity.value == "42 foobar"
    assert entity.unit == ""


def test_entity_info_string_with_existing_unit_not_overwritten() -> None:
    """Test STRING value is not parsed when unit field is already set."""
    entity = EntityInfo(
        name="Already has unit",
        value="7968 kWh",
        unit="something",
        desc="",
        data_type=DataType.STRING,
    )

    assert entity.value == "7968 kWh"
    assert entity.unit == "something"


def test_entity_info_string_plain_text_not_parsed() -> None:
    """Test regular STRING value without number-unit pattern is kept as-is."""
    entity = EntityInfo(
        name="Firmware version",
        value="1.0.38-20200730",
        unit="",
        desc="",
        data_type=DataType.STRING,
    )

    assert entity.value == "1.0.38-20200730"
    assert entity.unit == ""
