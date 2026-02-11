"""Tests for EntityInfo HA integration properties (device class, state class)."""

from bsblan.models import DataType, EntityInfo


def test_suggested_device_class_temperature_celsius() -> None:
    """Test suggested_device_class for °C unit."""
    entity = EntityInfo(
        name="Current Temperature",
        value="22.5",
        unit="°C",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "temperature"


def test_suggested_device_class_temperature_fahrenheit() -> None:
    """Test suggested_device_class for °F unit."""
    entity = EntityInfo(
        name="Current Temperature",
        value="72.5",
        unit="°F",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "temperature"


def test_suggested_device_class_temperature_html_encoded() -> None:
    """Test suggested_device_class for HTML-encoded degree symbol."""
    entity = EntityInfo(
        name="Outside Temperature",
        value="7.6",
        unit="&deg;C",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "temperature"


def test_suggested_device_class_temperature_numeric_encoded() -> None:
    """Test suggested_device_class for numeric HTML-encoded degree symbol."""
    entity = EntityInfo(
        name="Room Temperature",
        value="18.2",
        unit="&#176;C",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "temperature"


def test_suggested_device_class_energy_kwh() -> None:
    """Test suggested_device_class for kWh unit (energy counter)."""
    entity = EntityInfo(
        name="Energie utilisée",
        value="7538",
        unit="kWh",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "energy"


def test_suggested_device_class_energy_wh() -> None:
    """Test suggested_device_class for Wh unit."""
    entity = EntityInfo(
        name="Energy",
        value="100",
        unit="Wh",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "energy"


def test_suggested_device_class_energy_mwh() -> None:
    """Test suggested_device_class for MWh unit."""
    entity = EntityInfo(
        name="Energy Total",
        value="7.5",
        unit="MWh",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "energy"


def test_suggested_device_class_power_kw() -> None:
    """Test suggested_device_class for kW unit."""
    entity = EntityInfo(
        name="Power",
        value="3.5",
        unit="kW",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "power"


def test_suggested_device_class_power_w() -> None:
    """Test suggested_device_class for W unit."""
    entity = EntityInfo(
        name="Power",
        value="350",
        unit="W",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "power"


def test_suggested_device_class_pressure_bar() -> None:
    """Test suggested_device_class for bar unit."""
    entity = EntityInfo(
        name="Pressure",
        value="1.5",
        unit="bar",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "pressure"


def test_suggested_device_class_voltage() -> None:
    """Test suggested_device_class for V unit."""
    entity = EntityInfo(
        name="Voltage",
        value="230",
        unit="V",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "voltage"


def test_suggested_device_class_current() -> None:
    """Test suggested_device_class for A unit."""
    entity = EntityInfo(
        name="Current",
        value="5.2",
        unit="A",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "current"


def test_suggested_device_class_frequency() -> None:
    """Test suggested_device_class for Hz unit."""
    entity = EntityInfo(
        name="Frequency",
        value="50",
        unit="Hz",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "frequency"


def test_suggested_device_class_volume_flow_rate() -> None:
    """Test suggested_device_class for l/min unit."""
    entity = EntityInfo(
        name="Flow Rate",
        value="12",
        unit="l/min",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "volume_flow_rate"


def test_suggested_device_class_duration() -> None:
    """Test suggested_device_class for h unit."""
    entity = EntityInfo(
        name="Runtime",
        value="1500",
        unit="h",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "duration"


def test_suggested_device_class_percentage() -> None:
    """Test suggested_device_class for % unit."""
    entity = EntityInfo(
        name="COP",
        value="0.94",
        unit="%",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class == "power_factor"


def test_suggested_device_class_none_for_enum() -> None:
    """Test suggested_device_class returns None for ENUM with no unit."""
    entity = EntityInfo(
        name="Operating mode",
        value="3",
        unit="",
        desc="Comfort",
        data_type=DataType.ENUM,
    )
    assert entity.suggested_device_class is None


def test_suggested_device_class_none_for_unknown_unit() -> None:
    """Test suggested_device_class returns None for unknown units."""
    entity = EntityInfo(
        name="Unknown",
        value="42",
        unit="bbl",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_device_class is None


def test_suggested_state_class_energy_total_increasing() -> None:
    """Test suggested_state_class for energy counters is total_increasing."""
    entity = EntityInfo(
        name="Energie utilisée",
        value="7538",
        unit="kWh",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_state_class == "total_increasing"


def test_suggested_state_class_energy_mwh_total_increasing() -> None:
    """Test suggested_state_class for MWh is total_increasing."""
    entity = EntityInfo(
        name="Energy Total",
        value="7.5",
        unit="MWh",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_state_class == "total_increasing"


def test_suggested_state_class_energy_wh_total_increasing() -> None:
    """Test suggested_state_class for Wh is total_increasing."""
    entity = EntityInfo(
        name="Energy",
        value="100",
        unit="Wh",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_state_class == "total_increasing"


def test_suggested_state_class_temperature_measurement() -> None:
    """Test suggested_state_class for temperature is measurement."""
    entity = EntityInfo(
        name="Temperature",
        value="22.5",
        unit="°C",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_state_class == "measurement"


def test_suggested_state_class_power_measurement() -> None:
    """Test suggested_state_class for power is measurement."""
    entity = EntityInfo(
        name="Power",
        value="3.5",
        unit="kW",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_state_class == "measurement"


def test_suggested_state_class_pressure_measurement() -> None:
    """Test suggested_state_class for pressure is measurement."""
    entity = EntityInfo(
        name="Pressure",
        value="1.5",
        unit="bar",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_state_class == "measurement"


def test_suggested_state_class_none_for_enum() -> None:
    """Test suggested_state_class returns None for ENUM with no unit."""
    entity = EntityInfo(
        name="Operating mode",
        value="3",
        unit="",
        desc="Comfort",
        data_type=DataType.ENUM,
    )
    assert entity.suggested_state_class is None


def test_suggested_state_class_none_for_unknown_unit() -> None:
    """Test suggested_state_class returns None for unknown units."""
    entity = EntityInfo(
        name="Unknown",
        value="42",
        unit="bbl",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.suggested_state_class is None


def test_data_type_name_default() -> None:
    """Test data_type_name defaults to empty string."""
    entity = EntityInfo(
        name="Test",
        value="42",
        unit="kWh",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.data_type_name == ""


def test_data_type_family_default() -> None:
    """Test data_type_family defaults to empty string."""
    entity = EntityInfo(
        name="Test",
        value="42",
        unit="kWh",
        desc="",
        data_type=DataType.PLAIN_NUMBER,
    )
    assert entity.data_type_family == ""


def test_data_type_name_from_json() -> None:
    """Test data_type_name populated from JSON response."""
    entity = EntityInfo.from_dict(
        {
            "name": "Comfort setpoint",
            "dataType_name": "TEMP",
            "dataType_family": "VALS",
            "error": 0,
            "value": "18.0",
            "desc": "",
            "precision": 0.1,
            "dataType": 0,
            "readonly": 0,
            "readwrite": 0,
            "unit": "°C",
        }
    )
    assert entity.data_type_name == "TEMP"
    assert entity.data_type_family == "VALS"


def test_data_type_name_from_json_enum() -> None:
    """Test data_type_name for ENUM type from JSON response."""
    entity = EntityInfo.from_dict(
        {
            "name": "Operating mode",
            "dataType_name": "ENUM",
            "dataType_family": "ENUM",
            "error": 0,
            "value": "3",
            "desc": "Comfort",
            "dataType": 1,
            "readonly": 0,
            "readwrite": 0,
            "unit": "",
        }
    )
    assert entity.data_type_name == "ENUM"
    assert entity.data_type_family == "ENUM"


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
