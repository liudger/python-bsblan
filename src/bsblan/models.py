"""Models for BSB-Lan."""

from pydantic import BaseModel, Field


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
