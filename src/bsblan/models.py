"""Models for BSB-Lan."""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import time
from enum import IntEnum
from typing import Any

from mashumaro.mixins.json import DataClassJSONMixin

from bsblan.constants import TEMPERATURE_UNITS


@dataclass
class DHWTimeSwitchPrograms:
    """Dataclass for DHW time switch programs."""

    monday: str | None = None
    tuesday: str | None = None
    wednesday: str | None = None
    thursday: str | None = None
    friday: str | None = None
    saturday: str | None = None
    sunday: str | None = None
    standard_values: str | None = None


class DataType(IntEnum):
    """Enumeration of BSB-LAN data types."""

    PLAIN_NUMBER = 0  # Plain value (number)
    ENUM = 1  # Enumerated value with description
    BIT_VALUE = 2  # Bit value with bitmask and text
    WEEKDAY = 3  # Weekday
    TIME = 4  # Hour:minute
    DATETIME = 5  # Date and time
    DATE = 6  # Day and month
    STRING = 7  # String value
    PPS_TIME = 8  # PPS time (day of week, hour:minute)


@dataclass
class EntityInfo(DataClassJSONMixin):
    """Convert Data to valid keys and convert to object attributes.

    This object holds info about specific objects and handles automatic type conversion
    based on data_type and unit.

    Attributes:
        name: Name attribute.
        value: Value of attribute (type depends on data_type).
        unit: Unit of measurement.
        desc: Description of the entity.
        data_type: Type of data (see DataType enum).
        error: Error code (0 for no error).
        readonly: Whether the value is read-only.
        readwrite: Whether the value is read-write.
        precision: Optional precision for numeric values.

    """

    name: str = field(metadata={"alias": "name"})
    unit: str = field(metadata={"alias": "unit"})
    desc: str = field(metadata={"alias": "desc"})
    value: Any = field(metadata={"alias": "value"})
    data_type: int = field(metadata={"alias": "dataType"})
    error: int = field(default=0)
    readonly: int = field(default=0)
    readwrite: int = field(default=0)
    precision: float | None = field(default=None)

    def __post_init__(self) -> None:
        """Convert values based on data_type after initialization."""
        if self.value == "---":  # Special case for undefined values
            return

        try:
            self.value = self.convert_value()
        except (ValueError, TypeError) as e:
            logging.getLogger(__name__).warning(
                "Failed to convert value '%s' (type %s): %s",
                self.value,
                self.data_type,
                str(e),
            )

    def convert_value(self) -> Any:
        """Convert the value based on its data type.

        Returns:
            Any: The converted value.

        """
        result = self.value

        if self.data_type == DataType.PLAIN_NUMBER:
            # Handle temperature values
            if self._is_temperature():
                result = float(self.value)
            else:
                # Handle other numeric values
                with suppress(ValueError):
                    result = (
                        float(self.value) if "." in str(self.value) else int(self.value)
                    )

        elif self.data_type == DataType.ENUM:
            # For ENUMs, we keep the value as int but provide access to description
            with suppress(ValueError):
                result = int(self.value)

        elif self.data_type == DataType.TIME:
            # Convert HH:MM to time object
            try:
                hour, minute = map(int, str(self.value).split(":"))
                result = time(hour=hour, minute=minute)
            except ValueError:
                pass

        elif self.data_type == DataType.WEEKDAY:
            # Convert numeric weekday to int
            with suppress(ValueError):
                result = int(self.value)

        return result

    def _is_temperature(self) -> bool:
        """Check if the value represents a temperature.

        Returns:
            bool: True if the value represents a temperature.

        """
        return any(self.unit.endswith(unit) for unit in TEMPERATURE_UNITS)

    @property
    def enum_description(self) -> str | None:
        """Get the description for ENUM values.

        Returns:
            str | None: The description of the ENUM value, or None if not applicable.

        """
        return self.desc if self.data_type == DataType.ENUM else None


@dataclass
class State(DataClassJSONMixin):
    """Object that holds information about the state of a climate system."""

    hvac_mode: EntityInfo
    target_temperature: EntityInfo
    hvac_action: EntityInfo
    hvac_mode2: EntityInfo | None = None
    current_temperature: EntityInfo | None = None
    room1_thermostat_mode: EntityInfo | None = None
    room1_temp_setpoint_boost: EntityInfo | None = None


@dataclass
class StaticState(DataClassJSONMixin):
    """Class for entities that are not changing."""

    min_temp: EntityInfo
    max_temp: EntityInfo


@dataclass
class Sensor(DataClassJSONMixin):
    """Object holds info about object for sensor climate."""

    outside_temperature: EntityInfo
    current_temperature: EntityInfo | None = None


@dataclass
class HotWaterState(DataClassJSONMixin):  # pylint: disable=too-many-instance-attributes
    """Object holds info about object for hot water climate."""

    operating_mode: EntityInfo | None = None
    eco_mode_selection: EntityInfo | None = None
    nominal_setpoint: EntityInfo | None = None
    nominal_setpoint_max: EntityInfo | None = None
    reduced_setpoint: EntityInfo | None = None
    release: EntityInfo | None = None
    dhw_charging_priority: EntityInfo | None = None
    legionella_function: EntityInfo | None = None
    legionella_setpoint: EntityInfo | None = None
    legionella_periodicity: EntityInfo | None = None
    legionella_function_day: EntityInfo | None = None
    legionella_function_time: EntityInfo | None = None
    legionella_dwelling_time: EntityInfo | None = None
    legionella_circulation_pump: EntityInfo | None = None
    legionella_circulation_temp_diff: EntityInfo | None = None
    dhw_circulation_pump_release: EntityInfo | None = None
    dhw_circulation_pump_cycling: EntityInfo | None = None
    dhw_circulation_setpoint: EntityInfo | None = None
    operating_mode_changeover: EntityInfo | None = None
    dhw_actual_value_top_temperature: EntityInfo | None = None
    state_dhw_pump: EntityInfo | None = None
    dhw_time_program_monday: EntityInfo | None = None
    dhw_time_program_tuesday: EntityInfo | None = None
    dhw_time_program_wednesday: EntityInfo | None = None
    dhw_time_program_thursday: EntityInfo | None = None
    dhw_time_program_friday: EntityInfo | None = None
    dhw_time_program_saturday: EntityInfo | None = None
    dhw_time_program_sunday: EntityInfo | None = None
    dhw_time_program_standard_values: EntityInfo | None = None


@dataclass
class Device(DataClassJSONMixin):
    """Object holds bsblan device information."""

    name: str
    version: str
    MAC: str  # pylint: disable=invalid-name
    uptime: int


@dataclass
class Info(DataClassJSONMixin):
    """Object holding the heatingSystem info."""

    device_identification: EntityInfo
    controller_family: EntityInfo
    controller_variant: EntityInfo
