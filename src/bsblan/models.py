"""Models for BSB-Lan."""

from dataclasses import dataclass, field

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class EntityInfo(DataClassJSONMixin):
    """Convert Data to valid keys and convert to object attributes.

    This object holds info about specific objects.

    Attributes
    ----------
        name: Name attribute.
        value: value of attribute.

    """

    name: str = field(metadata={"alias": "name"})
    unit: str = field(metadata={"alias": "unit"})
    desc: str = field(metadata={"alias": "desc"})
    value: str = field(metadata={"alias": "value"})
    data_type: int = field(metadata={"alias": "dataType"})

    """
    "DataType" (
    0 = plain value (number),
    1 = ENUM (value (8/16 Bit) followed by space followed by text),
    2 = bit value (bit value (decimal)
      followed by bitmask followed by text/chosen option),
    3 = weekday,
    4 = hour:minute,
    5 = date and time,
    6 = day and month,
    7 = string,
    8 = PPS time (day of week, hour:minute))
    """


@dataclass
class State(DataClassJSONMixin):
    """Object that holds information about the state of a climate system.

    Attributes
    ----------
    hvac_mode : EntityInfo
        The HVAC mode of the climate system.
    hvac_mode2 : EntityInfo
        The second HVAC mode of the climate system.
    target_temperature : EntityInfo
        The target temperature of the climate system.
    hvac_action : EntityInfo
        The HVAC action of the climate system.
    current_temperature : EntityInfo
        The current temperature of the climate system.
    room1_thermostat_mode : EntityInfo
        The thermostat mode of the climate system.
    room1_temp_setpoint_boost : EntityInfo
        The temperature setpoint boost of the climate system.

    """

    hvac_mode: EntityInfo
    hvac_mode2: EntityInfo
    target_temperature: EntityInfo
    hvac_action: EntityInfo
    current_temperature: EntityInfo
    room1_thermostat_mode: EntityInfo
    room1_temp_setpoint_boost: EntityInfo


@dataclass
class StaticState(DataClassJSONMixin):
    """Class for entities that are not changing."""

    min_temp: EntityInfo
    max_temp: EntityInfo


@dataclass
class Sensor(DataClassJSONMixin):
    """Object holds info about object for sensor climate."""

    current_temperature: EntityInfo
    outside_temperature: EntityInfo


@dataclass
class HotWaterState(DataClassJSONMixin):
    """Object holds info about object for hot water climate."""

    operating_mode: EntityInfo
    nominal_setpoint: EntityInfo  # 1610
    nominal_setpoint_max: EntityInfo  # 1614
    reduced_setpoint: EntityInfo  # 1612
    release: EntityInfo  # 1620 - programme
    legionella_function: EntityInfo  # 1640 - Fixed weekday
    legionella_setpoint: EntityInfo  # 1645
    legionella_periodicity: EntityInfo  # 1641 - 7 (days)
    legionella_function_day: EntityInfo  # 1642 - Saturday
    legionella_function_time: EntityInfo  # 1643 - 12b:00
    dhw_actual_value_top_temperature: EntityInfo  # 8830
    state_dhw_pump: EntityInfo  # 8820


@dataclass
class Device(DataClassJSONMixin):
    """Object holds bsblan device information.

    Attributes
    ----------
        name: Name of the device.
        version: Firmware version of the device.
        MAC: MAC address of the device.

    """

    name: str
    version: str
    MAC: str  # pylint: disable=invalid-name
    uptime: int


@dataclass
class Info(DataClassJSONMixin):
    """Object holding the heatingSystem info.

    Attributes
    ----------
        name: Name of the sub-device.
        value: type of device.

    """

    device_identification: EntityInfo
    controller_family: EntityInfo
    controller_variant: EntityInfo
