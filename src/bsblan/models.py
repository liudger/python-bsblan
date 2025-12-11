"""Models for BSB-Lan."""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import time
from enum import IntEnum
from typing import Any, Final

from mashumaro.mixins.json import DataClassJSONMixin

from bsblan.constants import TEMPERATURE_UNITS

# Maximum number of time slots per day supported by BSB-LAN
MAX_TIME_SLOTS_PER_DAY: Final[int] = 3


@dataclass
class TimeSlot:
    """A single time slot with start and end time.

    Attributes:
        start: Start time of the slot.
        end: End time of the slot.

    Example:
        >>> slot = TimeSlot(time(6, 0), time(8, 0))
        >>> slot.to_bsblan_format()
        '06:00-08:00'

    """

    start: time
    end: time

    def __post_init__(self) -> None:
        """Validate that start is before end."""
        if self.start >= self.end:
            msg = f"Start time {self.start} must be before end time {self.end}"
            raise ValueError(msg)

    def to_bsblan_format(self) -> str:
        """Convert to BSB-LAN format 'HH:MM-HH:MM'.

        Returns:
            str: Time slot in BSB-LAN format.

        """
        return f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"

    @classmethod
    def from_bsblan_format(cls, value: str) -> TimeSlot:
        """Parse from BSB-LAN format 'HH:MM-HH:MM'.

        Args:
            value: Time slot string in format 'HH:MM-HH:MM'.

        Returns:
            TimeSlot: Parsed time slot.

        Raises:
            ValueError: If the format is invalid.

        """
        try:
            start_str, end_str = value.split("-")
            start_h, start_m = map(int, start_str.split(":"))
            end_h, end_m = map(int, end_str.split(":"))
            return cls(start=time(start_h, start_m), end=time(end_h, end_m))
        except (ValueError, AttributeError) as e:
            msg = f"Invalid time slot format: {value}"
            raise ValueError(msg) from e


@dataclass
class DaySchedule:
    """Schedule for a single day with up to 3 time slots (BSB-LAN limit).

    Attributes:
        slots: List of time slots for the day.

    Example:
        >>> schedule = DaySchedule(slots=[
        ...     TimeSlot(time(6, 0), time(8, 0)),
        ...     TimeSlot(time(17, 0), time(21, 0)),
        ... ])
        >>> schedule.to_bsblan_format()
        '06:00-08:00 17:00-21:00'

    """

    slots: list[TimeSlot] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate max 3 slots per day (BSB-LAN limitation)."""
        if len(self.slots) > MAX_TIME_SLOTS_PER_DAY:
            msg = (
                f"BSB-LAN supports maximum {MAX_TIME_SLOTS_PER_DAY} time slots per day"
            )
            raise ValueError(msg)

    def to_bsblan_format(self) -> str:
        """Convert to BSB-LAN string format like '06:00-08:00 17:00-21:00'.

        Returns:
            str: Day schedule in BSB-LAN format, or empty string if no slots.

        """
        if not self.slots:
            return ""
        return " ".join(slot.to_bsblan_format() for slot in self.slots)

    @classmethod
    def from_bsblan_format(cls, value: str) -> DaySchedule:
        """Parse from BSB-LAN format like '06:00-08:00 17:00-21:00'.

        Args:
            value: Day schedule string in BSB-LAN format.

        Returns:
            DaySchedule: Parsed day schedule.

        """
        if not value or value == "---":
            return cls(slots=[])
        slot_strings = value.split()
        slots = [TimeSlot.from_bsblan_format(s) for s in slot_strings]
        return cls(slots=slots)


@dataclass
class DHWSchedule:
    """Weekly hot water schedule for setting time programs.

    Use this dataclass to set DHW time programs via set_hot_water_schedule().
    Each day can have up to 3 time slots.

    Example:
        >>> schedule = DHWSchedule(
        ...     monday=DaySchedule(slots=[
        ...         TimeSlot(time(6, 0), time(8, 0)),
        ...         TimeSlot(time(17, 0), time(21, 0)),
        ...     ]),
        ...     tuesday=DaySchedule(slots=[
        ...         TimeSlot(time(6, 0), time(8, 0)),
        ...     ])
        ... )
        >>> await client.set_hot_water_schedule(schedule)

    """

    monday: DaySchedule | None = None
    tuesday: DaySchedule | None = None
    wednesday: DaySchedule | None = None
    thursday: DaySchedule | None = None
    friday: DaySchedule | None = None
    saturday: DaySchedule | None = None
    sunday: DaySchedule | None = None

    def has_any_schedule(self) -> bool:
        """Check if any day has a schedule set.

        Returns:
            bool: True if at least one day has a schedule.

        """
        return any(
            day is not None
            for day in [
                self.monday,
                self.tuesday,
                self.wednesday,
                self.thursday,
                self.friday,
                self.saturday,
                self.sunday,
            ]
        )


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
class SetHotWaterParam:
    """Parameters for setting hot water configuration.

    Use this dataclass to pass parameters to set_hot_water().
    Only one parameter should be set at a time (BSB-LAN API limitation).

    Note:
        This is for WRITING to the device. For READING hot water data,
        use HotWaterState, HotWaterConfig, or HotWaterSchedule.

    Attributes:
        nominal_setpoint: The nominal setpoint temperature (°C).
        reduced_setpoint: The reduced setpoint temperature (°C).
        nominal_setpoint_max: The maximum nominal setpoint temperature (°C).
        operating_mode: The operating mode (e.g., "0"=Off, "1"=On).
        dhw_time_programs: Time switch programs for DHW.
        eco_mode_selection: Eco mode selection.
        dhw_charging_priority: DHW charging priority.
        legionella_function_setpoint: Legionella function setpoint temperature (°C).
        legionella_function_periodicity: Legionella function periodicity.
        legionella_function_day: Day for legionella function.
        legionella_function_time: Time for legionella function (HH:MM).
        legionella_function_dwelling_time: Legionella dwelling time (minutes).
        operating_mode_changeover: Operating mode changeover.

    """

    nominal_setpoint: float | None = None
    reduced_setpoint: float | None = None
    nominal_setpoint_max: float | None = None
    operating_mode: str | None = None
    dhw_time_programs: DHWTimeSwitchPrograms | None = None
    eco_mode_selection: str | None = None
    dhw_charging_priority: str | None = None
    legionella_function_setpoint: float | None = None
    legionella_function_periodicity: str | None = None
    legionella_function_day: str | None = None
    legionella_function_time: str | None = None
    legionella_function_dwelling_time: float | None = None
    operating_mode_changeover: str | None = None


@dataclass
class State(DataClassJSONMixin):
    """Object that holds information about the state of a climate system."""

    hvac_mode: EntityInfo
    target_temperature: EntityInfo
    hvac_action: EntityInfo | None = None
    hvac_mode_changeover: EntityInfo | None = None
    current_temperature: EntityInfo | None = None
    room1_thermostat_mode: EntityInfo | None = None
    room1_temp_setpoint_boost: EntityInfo | None = None


@dataclass
class StaticState(DataClassJSONMixin):
    """Class for entities that are not changing."""

    min_temp: EntityInfo | None = None
    max_temp: EntityInfo | None = None


@dataclass
class Sensor(DataClassJSONMixin):
    """Object holds info about object for sensor climate."""

    outside_temperature: EntityInfo | None = None
    current_temperature: EntityInfo | None = None


@dataclass
class HotWaterState(DataClassJSONMixin):
    """Essential hot water state information (READ from device).

    This class contains only the most important hot water parameters
    that are typically checked frequently for monitoring purposes.

    Note:
        This is for READING from the device. For WRITING parameters,
        use SetHotWaterParam with set_hot_water().

    """

    operating_mode: EntityInfo | None = None
    nominal_setpoint: EntityInfo | None = None
    release: EntityInfo | None = None
    dhw_actual_value_top_temperature: EntityInfo | None = None
    state_dhw_pump: EntityInfo | None = None


@dataclass
class HotWaterConfig(DataClassJSONMixin):  # pylint: disable=too-many-instance-attributes
    """Hot water configuration and advanced settings (READ from device).

    This class contains configuration parameters that are typically
    set once and checked less frequently.

    Note:
        This is for READING from the device. For WRITING parameters,
        use SetHotWaterParam with set_hot_water().

    """

    eco_mode_selection: EntityInfo | None = None
    nominal_setpoint_max: EntityInfo | None = None
    reduced_setpoint: EntityInfo | None = None
    dhw_charging_priority: EntityInfo | None = None
    operating_mode_changeover: EntityInfo | None = None
    # Legionella protection settings
    legionella_function: EntityInfo | None = None
    legionella_function_setpoint: EntityInfo | None = None
    legionella_function_periodicity: EntityInfo | None = None
    legionella_function_day: EntityInfo | None = None
    legionella_function_time: EntityInfo | None = None
    legionella_function_dwelling_time: EntityInfo | None = None
    legionella_circulation_pump: EntityInfo | None = None
    legionella_circulation_temp_diff: EntityInfo | None = None
    # DHW circulation pump settings
    dhw_circulation_pump_release: EntityInfo | None = None
    dhw_circulation_pump_cycling: EntityInfo | None = None
    dhw_circulation_setpoint: EntityInfo | None = None


@dataclass
class HotWaterSchedule(DataClassJSONMixin):
    """Hot water time program schedules (READ from device).

    This class contains time program settings that are typically
    configured once and rarely changed.

    Note:
        This is for READING from the device. For WRITING time programs,
        use SetHotWaterParam with set_hot_water().

    """

    dhw_time_program_monday: EntityInfo | None = None
    dhw_time_program_tuesday: EntityInfo | None = None
    dhw_time_program_wednesday: EntityInfo | None = None
    dhw_time_program_thursday: EntityInfo | None = None
    dhw_time_program_friday: EntityInfo | None = None
    dhw_time_program_saturday: EntityInfo | None = None
    dhw_time_program_sunday: EntityInfo | None = None
    dhw_time_program_standard_values: EntityInfo | None = None


@dataclass
class DeviceTime(DataClassJSONMixin):
    """Object holds device time information."""

    time: EntityInfo


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
