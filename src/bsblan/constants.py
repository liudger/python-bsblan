"""BSBLAN constants."""

from __future__ import annotations

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
