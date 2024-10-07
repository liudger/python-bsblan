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


API_V1: Final[APIConfig] = {
    "heating": {
        "700": "hvac_mode",
        "710": "target_temperature",
        "900": "hvac_mode2",
        "8000": "hvac_action",
        "8740": "current_temperature",
        "8749": "room1_thermostat_mode",
    },
    "staticValues": {
        "714": "min_temp",
        "730": "max_temp",
    },
    "device": {
        "6224": "device_identification",
        "6225": "controller_family",
        "6226": "controller_variant",
    },
    "sensor": {
        "8700": "outside_temperature",
        "8740": "current_temperature",
    },
    "hot_water": {
        "1600": "operating_mode",
        "1610": "nominal_setpoint",
        "1612": "reduced_setpoint",
        "1620": "release",
        "1640": "legionella_function",
        "1645": "legionella_setpoint",
        "1641": "legionella_periodically",
    },
}

API_V3: Final[APIConfig] = {
    "heating": {
        "700": "hvac_mode",
        "710": "target_temperature",
        "900": "hvac_mode2",
        "8000": "hvac_action",
        "8740": "current_temperature",
        "8749": "room1_thermostat_mode",
        "770": "room1_temp_setpoint_boost",
    },
    "staticValues": {
        "714": "min_temp",
        "716": "max_temp",
    },
    "device": {
        "6224": "device_identification",
        "6225": "controller_family",
        "6226": "controller_variant",
    },
    "sensor": {
        "8700": "outside_temperature",
        "8740": "current_temperature",
    },
    "hot_water": {
        "1600": "operating_mode",
        "1610": "nominal_setpoint",
        "1612": "reduced_setpoint",
        "1620": "release",
        "1640": "legionella_function",
        "1645": "legionella_setpoint",
        "1641": "legionella_periodically",
    },
}

API_VERSIONS: Final[dict[str, APIConfig]] = {
    "v1": API_V1,
    "v3": API_V3,
}

# HVAC Modes
HVAC_MODE_DICT: Final[dict[int, str]] = {
    0: "off",
    1: "auto",
    2: "eco",
    3: "heat",
}

HVAC_MODE_DICT_REVERSE: Final[dict[str, int]] = {
    "off": 0,
    "auto": 1,
    "eco": 2,
    "heat": 3,
}

# Error Messages
INVALID_VALUES_ERROR_MSG: Final[str] = "Invalid values provided."
NO_STATE_ERROR_MSG: Final[str] = "No state provided."
VERSION_ERROR_MSG: Final[str] = "Version not supported"
FIRMWARE_VERSION_ERROR_MSG: Final[str] = "Firmware version not available"
TEMPERATURE_RANGE_ERROR_MSG: Final[str] = "Temperature range not initialized"
API_VERSION_ERROR_MSG: Final[str] = "API version not set"
MULTI_PARAMETER_ERROR_MSG: Final[str] = "Only one parameter can be set at a time"
SESSION_NOT_INITIALIZED_ERROR_MSG: Final[str] = "Session not initialized"
API_DATA_NOT_INITIALIZED_ERROR_MSG: Final[str] = "API data not initialized"


# Other Constants
DEFAULT_PORT: Final[int] = 80
SCAN_INTERVAL: Final[int] = 12  # seconds

# Configuration Keys
CONF_PASSKEY: Final[str] = "passkey"

# Attributes
ATTR_TARGET_TEMPERATURE: Final[str] = "target_temperature"
ATTR_INSIDE_TEMPERATURE: Final[str] = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE: Final[str] = "outside_temperature"
