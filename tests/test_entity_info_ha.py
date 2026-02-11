"""Tests for EntityInfo HA integration properties (device class, state class)."""

import pytest

from bsblan.models import DataType, EntityInfo

# -- suggested_device_class ------------------------------------------------


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("°C", "temperature"),
        ("°F", "temperature"),
        ("&deg;C", "temperature"),
        ("&deg;F", "temperature"),
        ("&#176;C", "temperature"),
        ("&#176;F", "temperature"),
        ("kWh", "energy"),
        ("Wh", "energy"),
        ("MWh", "energy"),
        ("kW", "power"),
        ("W", "power"),
        ("bar", "pressure"),
        ("Pa", "pressure"),
        ("hPa", "pressure"),
        ("V", "voltage"),
        ("A", "current"),
        ("mA", "current"),
        ("Hz", "frequency"),
        ("l/min", "volume_flow_rate"),
        ("l/h", "volume_flow_rate"),
        ("h", "duration"),
        ("min", "duration"),
        ("s", "duration"),
        ("%", "power_factor"),
    ],
)
def test_suggested_device_class(unit: str, expected: str) -> None:
    """Test suggested_device_class maps unit to correct HA device class."""
    entity = EntityInfo(
        name="Test",
        value="42",
        unit=unit,
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == expected


@pytest.mark.parametrize(
    ("unit", "data_type"),
    [
        ("", DataType.ENUM),
        ("bbl", DataType.PLAIN_NUMBER),
        ("unknown", DataType.PLAIN_NUMBER),
    ],
)
def test_suggested_device_class_none(unit: str, data_type: int) -> None:
    """Test suggested_device_class returns None for unmapped units."""
    entity = EntityInfo(
        name="Test",
        value="42",
        unit=unit,
        desc="",
        data_type=data_type,
    )
    assert entity.suggested_device_class is None


# -- suggested_state_class -------------------------------------------------


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("kWh", "total_increasing"),
        ("MWh", "total_increasing"),
        ("Wh", "total_increasing"),
        ("°C", "measurement"),
        ("°F", "measurement"),
        ("&deg;C", "measurement"),
        ("&#176;C", "measurement"),
        ("kW", "measurement"),
        ("W", "measurement"),
        ("bar", "measurement"),
        ("Pa", "measurement"),
        ("V", "measurement"),
        ("A", "measurement"),
        ("Hz", "measurement"),
        ("l/min", "measurement"),
        ("%", "measurement"),
    ],
)
def test_suggested_state_class(unit: str, expected: str) -> None:
    """Test suggested_state_class maps unit to correct HA state class."""
    entity = EntityInfo(
        name="Test",
        value="42",
        unit=unit,
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_state_class == expected


@pytest.mark.parametrize(
    ("unit", "data_type"),
    [
        ("", DataType.ENUM),
        ("bbl", DataType.PLAIN_NUMBER),
    ],
)
def test_suggested_state_class_none(unit: str, data_type: int) -> None:
    """Test suggested_state_class returns None for unmapped units."""
    entity = EntityInfo(
        name="Test",
        value="42",
        unit=unit,
        desc="",
        data_type=data_type,
    )
    assert entity.suggested_state_class is None


# -- dataType_name / dataType_family fields --------------------------------


def test_data_type_name_and_family_default() -> None:
    """Test data_type_name and data_type_family default to empty string."""
    entity = EntityInfo(
        name="Test",
        value="42",
        unit="kWh",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.data_type_name == ""
    assert entity.data_type_family == ""


@pytest.mark.parametrize(
    ("type_name", "type_family"),
    [
        ("TEMP", "VALS"),
        ("ENUM", "ENUM"),
    ],
)
def test_data_type_name_from_json(type_name: str, type_family: str) -> None:
    """Test data_type_name/family populated from JSON response."""
    entity = EntityInfo.from_dict(
        {
            "name": "Test",
            "dataType_name": type_name,
            "dataType_family": type_family,
            "error": 0,
            "value": "18.0",
            "desc": "",
            "dataType": 0,
            "readonly": 0,
            "unit": "°C",
        }
    )
    assert entity.data_type_name == type_name
    assert entity.data_type_family == type_family


# -- Backwards compatibility -----------------------------------------------


def test_backwards_compat_no_data_type_name_in_json() -> None:
    """Test EntityInfo works when JSON has no dataType_name/family."""
    entity = EntityInfo.from_dict(
        {
            "name": "Outside temp",
            "error": 0,
            "value": "7.6",
            "desc": "",
            "dataType": 0,
            "readonly": 0,
            "unit": "&deg;C",
        }
    )
    assert entity.data_type_name == ""
    assert entity.data_type_family == ""
    assert entity.suggested_device_class == "temperature"
    assert entity.suggested_state_class == "measurement"


def test_backwards_compat_existing_fields_unchanged() -> None:
    """Test that existing fields still work identically."""
    entity = EntityInfo(
        name="Test Temp",
        value="22.5",
        unit="°C",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    # Existing behavior: value converted to float for temperature
    assert entity.value == 22.5
    assert entity.name == "Test Temp"
    assert entity.unit == "°C"
    assert entity.data_type == DataType.PLAIN_NUMBER
    assert entity.error == 0
    assert entity.readonly == 0
    assert entity.readwrite == 0
    assert entity.precision is None
    assert entity.enum_description is None
