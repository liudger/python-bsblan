"""BSBLAN constants."""

DEVICE_INFO_API_V1 = {
    "6224": "device_identification",
    "6225": "controller_family",
    "6226": "controller_variant",
}

DEVICE_INFO_API_V3 = {
    "6224.0": "device_identification",
    "6225.0": "controller_family",
    "6226.0": "controller_variant",
}

HEATING_CIRCUIT1_API_V1 = {
    "700": "hvac_mode",
    "710": "target_temperature",
    "900": "hvac_mode2",
    "8000": "hvac_action",
    "8740": "current_temperature",
    "8749": "room1_thermostat_mode",
}

HEATING_CIRCUIT1_API_V3 = {
    "700.0": "hvac_mode",
    "710.0": "target_temperature",
    "900.0": "hvac_mode2",
    "8000.0": "hvac_action",
    "8740.0": "current_temperature",
    "8749.0": "room1_thermostat_mode",
}

STATIC_VALUES_API_V1 = {
    "714": "min_temp",
    "730": "max_temp",
}

STATIC_VALUES_API_V3 = {
    "714.0": "min_temp",
    "716.0": "max_temp",
}

SENSORS_API_V1 = {
    "8700": "outside_temperature",
    "8740": "current_temperature",
}
SENSORS_API_V3 = {
    "8700.0": "outside_temperature",
    "8740.0": "current_temperature",
}

HEATING_CIRCUIT2 = [
    "1000",
    "1010",
    "1011",
    "1012",
    "1014",
    "1030",
    "1200",
    "8001",  # status_heating_circuit2
    "8770",
]

# homeassistant values
HVAC_MODE_DICT = {
    0: "off",
    1: "auto",
    2: "eco",
    3: "heat",
}

HVAC_MODE_DICT_REVERSE = {
    "off": 0,
    "auto": 1,
    "eco": 2,
    "heat": 3,
}

INVALID_VALUES_ERROR_MSG = "Invalid values provided."
NO_STATE_ERROR_MSG = "No state provided."
VERSION_ERROR_MSG = "Version not supported"
