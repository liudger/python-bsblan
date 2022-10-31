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
    unit: str = Field(..., alias="unit")
    desc: str = Field(..., alias="desc")
    value: str = Field(..., alias="value")
    dataType: int = Field(..., alias="dataType")

    # "DataType" (
    # 0 = plain value (number),
    # 1 = ENUM (value (8/16 Bit) followed by space followed by text),
    # 2 = bit value (bit value (decimal)
    #   followed by bitmask followed by text/chosen option),
    # 3 = weekday,
    # 4 = hour:minute,
    # 5 = date and time,
    # 6 = day and month,
    # 7 = string,
    # 8 = PPS time (day of week, hour:minute))


class State(BaseModel):
    """This object holds info about object for state climate."""

    hvac_mode: EntityInfo
    hvac_mode2: EntityInfo
    target_temperature: EntityInfo
    target_temperature_high: EntityInfo
    target_temperature_low: EntityInfo
    min_temp: EntityInfo
    max_temp: EntityInfo
    hvac_action: EntityInfo
    current_temperature: EntityInfo
    room1_thermostat_mode: EntityInfo
    outside_temperature: EntityInfo


class Sensor(BaseModel):
    """This object holds info about object for sensor climate."""

    current_temperature: EntityInfo
    outside_temperature: EntityInfo


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
