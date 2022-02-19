"""Models for BSB-Lan."""

from pydantic import BaseModel, Field

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
    "700": "hvac_mode",
    "710": "target_temperature",
    "711": "target_temperature_high",
    "712": "target_temperature_low",
    "714": "min_temp",
    "730": "max_temp",
    "900": "hvac_action",
    "8000": "status_heating_circuit1",
    "8740": "current_temperature",
    "8749": "room1_thermostat_mode",
}
HEATING_CIRCUIT1_API_V2 = {
    "700": "hvac_mode",
    "710": "target_temperature",
    "711": "target_temperature_high",
    "712": "target_temperature_low",
    "714": "min_temp",
    "730": "max_temp",
    "900": "hvac_action",
    "8000": "status_heating_circuit1",
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


class EntityInfo(BaseModel):
    """Convert Data to valid keys and convert to object attributes.

    This object holds info about specific objects.

    Attributes:
        name: Name attribute.
        value: value of attribute.
    """

    name: str = Field(..., alias="name")
    value: str = Field(..., alias="value")
    unit: str = Field(..., alias="unit")
    desc: str = Field(..., alias="desc")


class State(BaseModel):
    """This object holds info about object for state climate."""

    hvac_mode: EntityInfo
    target_temperature: EntityInfo
    target_temperature_high: EntityInfo
    target_temperature_low: EntityInfo
    min_temp: EntityInfo
    max_temp: EntityInfo
    hvac_action: EntityInfo
    status_heating_circuit1: EntityInfo
    current_temperature: EntityInfo
    room1_thermostat_mode: EntityInfo


class Device(BaseModel):
    """This object holds bsblan device information.

    Attributes:
        name: Name of the device.
        version: Firmware version of the device.
        MAC: MAC address of the device.

    """

    name: str = Field(..., alias="name")
    version: str = Field(..., alias="version")
    MAC: str = Field(..., alias="MAC")
    uptime: int = Field(..., alias="uptime")


class Info(BaseModel):
    """Object holding the heatingsystem info.

    Attributes:
        name: Name of the sub-device.
        value: type of device.
    """

    device_identification: EntityInfo
    controller_family: EntityInfo
    controller_variant: EntityInfo
