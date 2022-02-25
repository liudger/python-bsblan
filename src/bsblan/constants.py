"""BSBLAN constants."""

DEVICE_INFO_API_V1 = {
    "6224": "device_identification",
    "6225": "controller_family",
    "6226": "controller_variant",
}
DEVICE_INFO_API_V2 = {
    "6224": "device_identification",
    "6225": "controller_family",
    "6226": "controller_variant",
}
# dict of parameter needed for climate device.
# need to update values and request less?
HEATING_CIRCUIT1_API_V1 = {
    "700": "preset_mode",
    "710": "target_temperature",
    "711": "target_temperature_high",
    "712": "target_temperature_low",
    "714": "min_temp",
    "730": "max_temp",
    "900": "preset_mode2",
    "8000": "hvac_action",
    "8700": "outside_temperature",
    "8740": "current_temperature",
    "8749": "room1_thermostat_mode",
}
HEATING_CIRCUIT1_API_V2 = {
    "700": "preset_mode",
    "710": "target_temperature",
    "711": "target_temperature_high",
    "712": "target_temperature_low",
    "714": "min_temp",
    "730": "max_temp",
    "900": "preset_mode2",
    "8000": "hvac_action",
    "8700": "outside_temperature",
    "8740": "current_temperature room1",
    "8749": "room1_thermostat_mode",
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
PRESET_MODE_DICT = {
    0: "protection_mode",
    1: "auto",
    2: "reduced",
    3: "comfort",
}
PRESET_MODE_DICT_REVERSE = {
    "protection_mode": 0,
    "auto": 1,
    "reduced": 2,
    "comfort": 3,
}
