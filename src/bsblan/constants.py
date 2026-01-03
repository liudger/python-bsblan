"""BSBLAN constants."""

from __future__ import annotations

from enum import IntEnum
from typing import Final, TypedDict


# API Versions
class APIConfig(TypedDict):
    """Type for API configuration."""

    heating: dict[str, str]
    staticValues: dict[str, str]
    device: dict[str, str]
    sensor: dict[str, str]
    hot_water: dict[str, str]


# Base parameters that exist in all API versions
BASE_HEATING_PARAMS: Final[dict[str, str]] = {
    "700": "hvac_mode",
    "710": "target_temperature",
    "900": "hvac_mode_changeover",
    # -------
    "8000": "hvac_action",
    "8740": "current_temperature",
    "8749": "room1_thermostat_mode",
}

BASE_STATIC_VALUES_PARAMS: Final[dict[str, str]] = {
    "714": "min_temp",
}

BASE_DEVICE_PARAMS: Final[dict[str, str]] = {
    "6224": "device_identification",
    "6225": "controller_family",
    "6226": "controller_variant",
}

BASE_SENSOR_PARAMS: Final[dict[str, str]] = {
    "8700": "outside_temperature",
    "8740": "current_temperature",
}

BASE_HOT_WATER_PARAMS: Final[dict[str, str]] = {
    "1600": "operating_mode",
    "1601": "eco_mode_selection",
    "1610": "nominal_setpoint",
    "1614": "nominal_setpoint_max",
    "1612": "reduced_setpoint",
    "1620": "release",
    "1630": "dhw_charging_priority",
    "1640": "legionella_function",
    "1641": "legionella_function_periodicity",
    "1642": "legionella_function_day",
    "1644": "legionella_function_time",
    "1645": "legionella_function_setpoint",
    "1646": "legionella_function_dwelling_time",
    "1647": "legionella_circulation_pump",
    "1648": "legionella_circulation_temp_diff",
    "1660": "dhw_circulation_pump_release",
    "1661": "dhw_circulation_pump_cycling",
    "1663": "dhw_circulation_setpoint",
    "1680": "operating_mode_changeover",
    # -------
    "8830": "dhw_actual_value_top_temperature",
    "8820": "state_dhw_pump",
    # -------
    "561": "dhw_time_program_monday",
    "562": "dhw_time_program_tuesday",
    "563": "dhw_time_program_wednesday",
    "564": "dhw_time_program_thursday",
    "565": "dhw_time_program_friday",
    "566": "dhw_time_program_saturday",
    "567": "dhw_time_program_sunday",
    "576": "dhw_time_program_standard_values",
}

# V1-specific parameters
V1_STATIC_VALUES_EXTENSIONS: Final[dict[str, str]] = {
    "730": "max_temp",  # V1 uses 730 for max_temp
}

# V3-specific additional parameters
V3_HEATING_EXTENSIONS: Final[dict[str, str]] = {
    "770": "room1_temp_setpoint_boost",
    # Future V3 extensions like 701, 701.1, 701.2 can be added here
}

V3_STATIC_VALUES_EXTENSIONS: Final[dict[str, str]] = {
    "716": "max_temp",  # V3 uses 716 for max_temp
}


def build_api_config(version: str) -> APIConfig:
    """Build API configuration dynamically based on version.

    Args:
        version: The API version ("v1" or "v3")

    Returns:
        APIConfig: The complete API configuration for the specified version

    """
    config: APIConfig = {
        "heating": BASE_HEATING_PARAMS.copy(),
        "staticValues": BASE_STATIC_VALUES_PARAMS.copy(),
        "device": BASE_DEVICE_PARAMS.copy(),
        "sensor": BASE_SENSOR_PARAMS.copy(),
        "hot_water": BASE_HOT_WATER_PARAMS.copy(),
    }

    if version == "v1":
        config["staticValues"].update(V1_STATIC_VALUES_EXTENSIONS)
    elif version == "v3":
        config["heating"].update(V3_HEATING_EXTENSIONS)
        config["staticValues"].update(V3_STATIC_VALUES_EXTENSIONS)

    return config


# Pre-built API configurations
API_V1: Final[APIConfig] = build_api_config("v1")
API_V3: Final[APIConfig] = build_api_config("v3")

API_VERSIONS: Final[dict[str, APIConfig]] = {
    "v1": API_V1,
    "v3": API_V3,
}

# Valid HVAC mode values for validation
VALID_HVAC_MODES: Final[set[int]] = {0, 1, 2, 3}


class HVACActionCategory(IntEnum):
    """Categories for HVAC action states.

    These represent the simplified action states that can be used
    by home automation systems like Home Assistant.
    """

    HEATING = 1
    COOLING = 2
    PREHEATING = 3
    DRYING = 4
    FAN = 5
    OFF = 6
    DEFROSTING = 7
    IDLE = 0  # Default for unmapped status codes


class HeatingCircuitStatus(IntEnum):
    """BSB-LAN Parameter 8000 status codes for heating circuit 1.

    These are the vendor-specific status codes returned by BSB-LAN devices.
    Each status code has a descriptive name based on BSB-LAN documentation
    (LANG_DE_LEGACY.h / LANG_EN.h).

    Usage:
        >>> status = HeatingCircuitStatus(state.hvac_action.value)
        >>> print(status.name)  # e.g., "HEATING_COMFORT"
        >>> category = status.category  # e.g., HVACActionCategory.HEATING

    """

    # Off/Standby states
    FAULT_ERROR = 0x02
    STANDBY_1 = 0x19
    OFF = 0x76
    STANDBY_2 = 0x8C
    COOLING_OFF = 0x8A
    COOLING_LOCKED = 0x92
    HEATING_GENERATOR_OFF = 0xA1
    HEATING_OFF = 0xA2
    LOCKED_HEATING_MODE = 0xCC
    LOCKED_GENERATOR = 0xCD
    LOCKED_BUFFER = 0xCE

    # Heating states
    MANUAL_CONTROL = 0x04
    OVERRUN = 0x11
    FROST_PROTECTION_PLANT = 0x16
    FROST_PROTECTION = 0x17
    RESERVED_HEATING_1 = 0x18
    OVERHEAT_PROTECTION = 0x38
    ROOM_FROST_PROTECTION = 0x65
    LIMITED_BOILER_PROTECTION = 0x67
    LIMITED_DHW_PRIORITY = 0x68
    LIMITED_BUFFER = 0x69
    HEATING_LIMITED = 0x6A
    HEATING_COMFORT = 0x72
    SWITCHOFF_OPTIMIZATION = 0x73
    HEATING_REDUCED = 0x74
    FLOW_FROST_PROTECTION = 0x75
    DAY_ECO = 0x77
    SETBACK_REDUCED = 0x78
    SETBACK_FROST_PROTECTION = 0x79
    RESERVED_HEATING_2 = 0x89

    # Preheating states
    SWITCHON_OPTIMIZATION_QUICK_HEATUP = 0x6F
    SWITCHON_OPTIMIZATION = 0x70
    QUICK_HEATUP = 0x71

    # Drying state
    SCREED_FUNCTION = 0x66

    # Fan/Forced consumption states
    FORCED_CONSUMPTION_BUFFER = 0x6B
    FORCED_CONSUMPTION_DHW = 0x6C
    FORCED_CONSUMPTION_GENERATOR = 0x6D
    FORCED_CONSUMPTION = 0x6E

    # Cooling states
    COOLING_ACTIVE = 0x7F
    COOLING_PASSIVE = 0x80
    COOLING_EVAPORATOR = 0x81
    COOLING_RELATED_1 = 0x84
    DEW_POINT_MONITOR = 0x85
    COOLING_LIMIT_OUTDOOR_TEMP = 0x86
    COOLING_MODE = 0x88
    RECOOLING_DHW_HC = 0x8E
    COOLING_LIMITED = 0x90
    COOLING_LIMIT_OUTSIDE_TEMP_MAX = 0x91
    RESERVED_COOLING_1 = 0x94
    RESERVED_COOLING_2 = 0x95
    COOLING_COMFORT = 0x96
    LIMIT_FLOW_DEW_POINT = 0xB1
    LIMIT_FLOW_OUTDOOR_TEMP = 0xB2
    FLOW_LIMIT_REACHED = 0xB3
    LIMIT_SOURCE_TEMP_MIN_COOLING = 0xC4
    COMPRESSOR_RUNTIME_MIN_COOLING = 0xCF
    COMPRESSOR_1_AND_2_COOLING = 0xD0
    COMPRESSOR_1_COOLING = 0xD1
    COMPRESSOR_2_COOLING = 0xD2
    PROTECTION_MODE_COOLING = 0x11D

    # Defrosting states
    DEFROST = 0x7D
    DRIP_OFF = 0x7E
    PREHEAT_DEFROST = 0x82
    DEFROST_RELATED_1 = 0x83
    FORCED_DEFROST_COMPRESSOR = 0xC0
    FORCED_DEFROST_FAN = 0xC1
    DEFROST_COMPRESSOR = 0xC2
    DEFROST_FAN = 0xC3
    FROST_PROTECTION_COOLING = 0xCA
    DEFROST_RELATED_2 = 0x101

    @property
    def category(self) -> HVACActionCategory:
        """Get the HVAC action category for this status code.

        Returns:
            HVACActionCategory: The category this status belongs to.

        """
        return _STATUS_TO_CATEGORY.get(self, HVACActionCategory.IDLE)

    @classmethod
    def from_value(cls, value: int) -> HeatingCircuitStatus | None:
        """Create a HeatingCircuitStatus from a raw value.

        Args:
            value: The raw status code from BSB-LAN parameter 8000.

        Returns:
            HeatingCircuitStatus if the value is known, None otherwise.

        """
        try:
            return cls(value)
        except ValueError:
            return None


# Internal mapping from status codes to categories
_STATUS_TO_CATEGORY: dict[HeatingCircuitStatus, HVACActionCategory] = {
    # Off states
    HeatingCircuitStatus.FAULT_ERROR: HVACActionCategory.OFF,
    HeatingCircuitStatus.STANDBY_1: HVACActionCategory.OFF,
    HeatingCircuitStatus.OFF: HVACActionCategory.OFF,
    HeatingCircuitStatus.STANDBY_2: HVACActionCategory.OFF,
    HeatingCircuitStatus.COOLING_OFF: HVACActionCategory.OFF,
    HeatingCircuitStatus.COOLING_LOCKED: HVACActionCategory.OFF,
    HeatingCircuitStatus.HEATING_GENERATOR_OFF: HVACActionCategory.OFF,
    HeatingCircuitStatus.HEATING_OFF: HVACActionCategory.OFF,
    HeatingCircuitStatus.LOCKED_HEATING_MODE: HVACActionCategory.OFF,
    HeatingCircuitStatus.LOCKED_GENERATOR: HVACActionCategory.OFF,
    HeatingCircuitStatus.LOCKED_BUFFER: HVACActionCategory.OFF,
    # Heating states
    HeatingCircuitStatus.MANUAL_CONTROL: HVACActionCategory.HEATING,
    HeatingCircuitStatus.OVERRUN: HVACActionCategory.HEATING,
    HeatingCircuitStatus.FROST_PROTECTION_PLANT: HVACActionCategory.HEATING,
    HeatingCircuitStatus.FROST_PROTECTION: HVACActionCategory.HEATING,
    HeatingCircuitStatus.RESERVED_HEATING_1: HVACActionCategory.HEATING,
    HeatingCircuitStatus.OVERHEAT_PROTECTION: HVACActionCategory.HEATING,
    HeatingCircuitStatus.ROOM_FROST_PROTECTION: HVACActionCategory.HEATING,
    HeatingCircuitStatus.LIMITED_BOILER_PROTECTION: HVACActionCategory.HEATING,
    HeatingCircuitStatus.LIMITED_DHW_PRIORITY: HVACActionCategory.HEATING,
    HeatingCircuitStatus.LIMITED_BUFFER: HVACActionCategory.HEATING,
    HeatingCircuitStatus.HEATING_LIMITED: HVACActionCategory.HEATING,
    HeatingCircuitStatus.HEATING_COMFORT: HVACActionCategory.HEATING,
    HeatingCircuitStatus.SWITCHOFF_OPTIMIZATION: HVACActionCategory.HEATING,
    HeatingCircuitStatus.HEATING_REDUCED: HVACActionCategory.HEATING,
    HeatingCircuitStatus.FLOW_FROST_PROTECTION: HVACActionCategory.HEATING,
    HeatingCircuitStatus.DAY_ECO: HVACActionCategory.HEATING,
    HeatingCircuitStatus.SETBACK_REDUCED: HVACActionCategory.HEATING,
    HeatingCircuitStatus.SETBACK_FROST_PROTECTION: HVACActionCategory.HEATING,
    HeatingCircuitStatus.RESERVED_HEATING_2: HVACActionCategory.HEATING,
    # Preheating states
    HeatingCircuitStatus.SWITCHON_OPTIMIZATION_QUICK_HEATUP: (
        HVACActionCategory.PREHEATING
    ),
    HeatingCircuitStatus.SWITCHON_OPTIMIZATION: HVACActionCategory.PREHEATING,
    HeatingCircuitStatus.QUICK_HEATUP: HVACActionCategory.PREHEATING,
    # Drying state
    HeatingCircuitStatus.SCREED_FUNCTION: HVACActionCategory.DRYING,
    # Fan states
    HeatingCircuitStatus.FORCED_CONSUMPTION_BUFFER: HVACActionCategory.FAN,
    HeatingCircuitStatus.FORCED_CONSUMPTION_DHW: HVACActionCategory.FAN,
    HeatingCircuitStatus.FORCED_CONSUMPTION_GENERATOR: HVACActionCategory.FAN,
    HeatingCircuitStatus.FORCED_CONSUMPTION: HVACActionCategory.FAN,
    # Cooling states
    HeatingCircuitStatus.COOLING_ACTIVE: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COOLING_PASSIVE: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COOLING_EVAPORATOR: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COOLING_RELATED_1: HVACActionCategory.COOLING,
    HeatingCircuitStatus.DEW_POINT_MONITOR: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COOLING_LIMIT_OUTDOOR_TEMP: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COOLING_MODE: HVACActionCategory.COOLING,
    HeatingCircuitStatus.RECOOLING_DHW_HC: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COOLING_LIMITED: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COOLING_LIMIT_OUTSIDE_TEMP_MAX: HVACActionCategory.COOLING,
    HeatingCircuitStatus.RESERVED_COOLING_1: HVACActionCategory.COOLING,
    HeatingCircuitStatus.RESERVED_COOLING_2: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COOLING_COMFORT: HVACActionCategory.COOLING,
    HeatingCircuitStatus.LIMIT_FLOW_DEW_POINT: HVACActionCategory.COOLING,
    HeatingCircuitStatus.LIMIT_FLOW_OUTDOOR_TEMP: HVACActionCategory.COOLING,
    HeatingCircuitStatus.FLOW_LIMIT_REACHED: HVACActionCategory.COOLING,
    HeatingCircuitStatus.LIMIT_SOURCE_TEMP_MIN_COOLING: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COMPRESSOR_RUNTIME_MIN_COOLING: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COMPRESSOR_1_AND_2_COOLING: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COMPRESSOR_1_COOLING: HVACActionCategory.COOLING,
    HeatingCircuitStatus.COMPRESSOR_2_COOLING: HVACActionCategory.COOLING,
    HeatingCircuitStatus.PROTECTION_MODE_COOLING: HVACActionCategory.COOLING,
    # Defrosting states
    HeatingCircuitStatus.DEFROST: HVACActionCategory.DEFROSTING,
    HeatingCircuitStatus.DRIP_OFF: HVACActionCategory.DEFROSTING,
    HeatingCircuitStatus.PREHEAT_DEFROST: HVACActionCategory.DEFROSTING,
    HeatingCircuitStatus.DEFROST_RELATED_1: HVACActionCategory.DEFROSTING,
    HeatingCircuitStatus.FORCED_DEFROST_COMPRESSOR: HVACActionCategory.DEFROSTING,
    HeatingCircuitStatus.FORCED_DEFROST_FAN: HVACActionCategory.DEFROSTING,
    HeatingCircuitStatus.DEFROST_COMPRESSOR: HVACActionCategory.DEFROSTING,
    HeatingCircuitStatus.DEFROST_FAN: HVACActionCategory.DEFROSTING,
    HeatingCircuitStatus.FROST_PROTECTION_COOLING: HVACActionCategory.DEFROSTING,
    HeatingCircuitStatus.DEFROST_RELATED_2: HVACActionCategory.DEFROSTING,
}


def get_hvac_action_category(status_code: int) -> HVACActionCategory:
    """Get the HVAC action category for a given status code.

    This is a convenience function for getting the category of any status code,
    including unknown ones (which return IDLE).

    Args:
        status_code: The raw status code from BSB-LAN parameter 8000.

    Returns:
        HVACActionCategory: The category for this status code.

    Example:
        >>> category = get_hvac_action_category(0x72)
        >>> print(category)  # HVACActionCategory.HEATING
        >>> print(category.name)  # "HEATING"

    """
    status = HeatingCircuitStatus.from_value(status_code)
    if status is None:
        return HVACActionCategory.IDLE
    return status.category


# Error Messages
NO_STATE_ERROR_MSG: Final[str] = "No state provided."
NO_SCHEDULE_ERROR_MSG: Final[str] = "No schedule provided."
VERSION_ERROR_MSG: Final[str] = "Version not supported"
FIRMWARE_VERSION_ERROR_MSG: Final[str] = "Firmware version not available"
TEMPERATURE_RANGE_ERROR_MSG: Final[str] = "Temperature range not initialized"
API_VERSION_ERROR_MSG: Final[str] = "API version not set"
MULTI_PARAMETER_ERROR_MSG: Final[str] = "Only one parameter can be set at a time"
SESSION_NOT_INITIALIZED_ERROR_MSG: Final[str] = "Session not initialized"
API_DATA_NOT_INITIALIZED_ERROR_MSG: Final[str] = "API data not initialized"
API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG: Final[str] = "API validator not initialized"

# Time validation constants
MIN_VALID_YEAR: Final[int] = 1900  # Reasonable minimum year for BSB-LAN devices
MAX_VALID_YEAR: Final[int] = 2100  # Reasonable maximum year for BSB-LAN devices

# Handle both ASCII and Unicode degree symbols
TEMPERATURE_UNITS = {"°C", "°F", "&#176;C", "&#176;F", "&deg;C", "&deg;F"}

# Hot Water Parameter Groups
# Essential parameters for frequent monitoring
HOT_WATER_ESSENTIAL_PARAMS: Final[set[str]] = {
    param_id
    for param_id, name in BASE_HOT_WATER_PARAMS.items()
    if name
    in {
        "operating_mode",
        "nominal_setpoint",
        "release",
        "dhw_actual_value_top_temperature",
        "state_dhw_pump",
    }
}

# Configuration parameters checked less frequently
HOT_WATER_CONFIG_PARAMS: Final[set[str]] = {
    param_id
    for param_id, name in BASE_HOT_WATER_PARAMS.items()
    if name
    in {
        "eco_mode_selection",
        "nominal_setpoint_max",
        "reduced_setpoint",
        "dhw_charging_priority",
        "operating_mode_changeover",
        "legionella_function",
        "legionella_function_setpoint",
        "legionella_function_periodicity",
        "legionella_function_day",
        "legionella_function_time",
        "legionella_function_dwelling_time",
        "legionella_circulation_pump",
        "legionella_circulation_temp_diff",
        "dhw_circulation_pump_release",
        "dhw_circulation_pump_cycling",
        "dhw_circulation_setpoint",
    }
}

# Schedule parameters (time programs)
HOT_WATER_SCHEDULE_PARAMS: Final[set[str]] = {
    param_id
    for param_id, name in BASE_HOT_WATER_PARAMS.items()
    if name
    in {
        "dhw_time_program_monday",
        "dhw_time_program_tuesday",
        "dhw_time_program_wednesday",
        "dhw_time_program_thursday",
        "dhw_time_program_friday",
        "dhw_time_program_saturday",
        "dhw_time_program_sunday",
        "dhw_time_program_standard_values",
    }
}

# Settable hot water parameters mapping (param_id -> attribute name)
# Used by set_hot_water to map SetHotWaterParam attributes to BSB-LAN parameter IDs
SETTABLE_HOT_WATER_PARAMS: Final[dict[str, str]] = {
    "1610": "nominal_setpoint",
    "1612": "reduced_setpoint",
    "1614": "nominal_setpoint_max",
    "1600": "operating_mode",
    "1601": "eco_mode_selection",
    "1630": "dhw_charging_priority",
    "1645": "legionella_function_setpoint",
    "1641": "legionella_function_periodicity",
    "1642": "legionella_function_day",
    "1644": "legionella_function_time",
    "1646": "legionella_function_dwelling_time",
    "1680": "operating_mode_changeover",
}

# DHW time program parameter mappings
DHW_TIME_PROGRAM_PARAMS: Final[dict[str, str]] = {
    "561": "monday",
    "562": "tuesday",
    "563": "wednesday",
    "564": "thursday",
    "565": "friday",
    "566": "saturday",
    "567": "sunday",
    "576": "standard_values",
}
