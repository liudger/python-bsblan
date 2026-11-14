"""Models for BSB-Lan."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import time
from enum import IntEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bsblan.constants import (
    TEMPERATURE_UNITS,
    UNIT_DEVICE_CLASS_MAP,
    UNIT_STATE_CLASS_MAP,
)

# All possible EntityInfo value types after conversion
EntityValue = float | int | str | time

# TypeVar for EntityInfo generic
T = TypeVar("T", bound=EntityValue)


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
    TIMEPROG = 9  # Time program (schedule slots)


def _convert_bsblan_value(
    raw_value: Any,
    data_type: int,
    unit: str,
) -> EntityValue | None:
    """Convert a raw BSB-LAN value to the appropriate Python type.

    Args:
        raw_value: The raw value from the BSB-LAN API.
        data_type: The BSB-LAN data type code.
        unit: The unit of measurement.

    Returns:
        The converted value, or None if the value is inactive.

    """
    # BSB-LAN's `replaceDisabled` setting decides what the firmware sends for a
    # deactivated/inactive numeric parameter. It defaults to "---", but its own
    # BSB_LAN_config.h documents "None" as the value Home Assistant users should
    # pick, so both spellings reach us in the wild.
    if raw_value is None or raw_value in {"---", "", "None"}:
        return None

    raw = str(raw_value)
    result: EntityValue = raw

    try:
        if data_type == DataType.PLAIN_NUMBER:
            if any(unit.endswith(u) for u in TEMPERATURE_UNITS):
                result = float(raw)
            else:
                result = float(raw) if "." in raw else int(raw)

        elif data_type == DataType.ENUM:
            result = int(raw)

        elif data_type == DataType.TIME:
            hour, minute = map(int, raw.split(":"))
            result = time(hour=hour, minute=minute)

        elif data_type == DataType.WEEKDAY:
            result = int(raw)

    except (ValueError, TypeError) as e:
        logging.getLogger(__name__).warning(
            "Failed to convert value '%s' (type %s): %s",
            raw_value,
            data_type,
            str(e),
        )

    return result


class EntityInfo(BaseModel, Generic[T]):
    """BSB-LAN parameter info with automatic type conversion.

    This object holds info about specific objects and handles automatic type
    conversion based on data_type and unit.

    The generic parameter ``T`` indicates the expected value type after
    conversion:

    - ``EntityInfo[float]`` for temperature / numeric sensor values
    - ``EntityInfo[int]`` for enums, weekdays and plain integers
    - ``EntityInfo[time]`` for HH:MM time values
    - ``EntityInfo[str]`` for string / datetime values

    When the device returns ``"---"`` or ``"None"`` (sensor not in use, per
    BSB-LAN's ``replaceDisabled`` setting), ``value`` is set
    to ``None``.

    Attributes:
        name: Name attribute.
        value: Converted value, or None when sensor/parameter is inactive.
        unit: Unit of measurement.
        desc: Description of the entity.
        data_type: Type of data (see DataType enum).
        error: Error code (0 for no error).
        readonly: Whether the value is read-only.
        readwrite: Whether the value is read-write.
        precision: Optional precision for numeric values.
        data_type_name: BSB-LAN data type name (e.g., "TEMP", "ENUM").
        data_type_family: BSB-LAN data type family (e.g., "VALS", "ENUM").

    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    name: str
    unit: str
    desc: str
    value: T | None = None
    data_type: int = Field(validation_alias="dataType", default=0)
    error: int = 0
    readonly: int = 0
    readwrite: int = 0
    precision: float | None = None
    data_type_name: str = Field(default="", validation_alias="dataType_name")
    data_type_family: str = Field(default="", validation_alias="dataType_family")

    @model_validator(mode="before")
    @classmethod
    def convert_raw_value(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Convert raw string values before pydantic validates types.

        BSB-LAN always sends values as strings. This validator converts
        them to the correct Python type (float, int, time) before
        pydantic's type checking runs.

        Some STRING-type parameters (e.g. "7968 kWh") embed a numeric
        value with a unit suffix.  When the ``unit`` field is empty and
        the value matches ``<number> <known-unit>``, the numeric part is
        extracted and the ``unit`` field is populated automatically.
        """
        raw_value = data.get("value")
        # Resolve data_type from either alias or field name
        data_type = data.get("dataType", data.get("data_type", 0))
        unit = data.get("unit", "")

        data["value"] = _convert_bsblan_value(raw_value, data_type, unit)

        # Handle STRING values with embedded units (e.g. "7968 kWh")
        converted = data["value"]
        if isinstance(converted, str) and not unit and data_type == DataType.STRING:
            match = re.match(r"^(\d+(?:\.\d+)?)\s+(\S+)$", converted)
            if match and match.group(2) in UNIT_DEVICE_CLASS_MAP:
                num_str = match.group(1)
                data["value"] = float(num_str) if "." in num_str else int(num_str)
                data["unit"] = match.group(2)

        return data

    @property
    def enum_description(self) -> str | None:
        """Get the description for ENUM values.

        Returns:
            str | None: The description of the ENUM value, or None.

        """
        return self.desc if self.data_type == DataType.ENUM else None

    @property
    def suggested_device_class(self) -> str | None:
        """Suggest HA SensorDeviceClass based on unit and data type.

        Only PLAIN_NUMBER data types are considered sensor-like values.
        Returns None for ENUM, TIME, WEEKDAY, STRING, and other
        non-numeric types even if they carry a unit.

        Returns:
            str | None: The suggested HA device class (e.g., "temperature",
                "energy", "power"), or None if no mapping exists or the
                data type is not numeric.

        """
        if self.data_type != DataType.PLAIN_NUMBER:
            return None
        return UNIT_DEVICE_CLASS_MAP.get(self.unit)

    @property
    def suggested_state_class(self) -> str | None:
        """Suggest HA SensorStateClass based on unit and data type.

        Only PLAIN_NUMBER data types are considered sensor-like values.
        Returns None for ENUM, TIME, WEEKDAY, STRING, and other
        non-numeric types even if they carry a unit.

        Energy counters (kWh, MWh, Wh) are mapped to "total_increasing",
        while other numeric measurements use "measurement".

        Returns:
            str | None: The suggested HA state class (e.g., "measurement",
                "total_increasing"), or None if the data type is not
                numeric or no mapping exists.

        """
        if self.data_type != DataType.PLAIN_NUMBER:
            return None
        return UNIT_STATE_CLASS_MAP.get(self.unit)


@dataclass
class SetHotWaterParam:
    """Parameters for setting hot water configuration.

    Use this dataclass to pass parameters to set_hot_water().
    Only one parameter should be set at a time (BSB-LAN API limitation).

    Note:
        This is for WRITING to the device. For READING hot water data,
        use HotWaterState or HotWaterConfig. Schedules use bsblan.schedules.

    Attributes:
        nominal_setpoint: The nominal setpoint temperature.
        reduced_setpoint: The reduced setpoint temperature.
        nominal_setpoint_max: The maximum nominal setpoint temperature.
        operating_mode: The operating mode (e.g., "0"=Off, "1"=On).
        eco_mode_selection: Eco mode selection.
        dhw_charging_priority: DHW charging priority.
        legionella_function_setpoint: Legionella function setpoint temperature.
        legionella_function_periodicity: Legionella function periodicity.
        legionella_function_day: Day for legionella function.
        legionella_function_time: Time for legionella function (HH:MM).
        legionella_function_dwelling_time: Legionella dwelling time (min).
        operating_mode_changeover: Operating mode changeover.

    """

    nominal_setpoint: float | None = None
    reduced_setpoint: float | None = None
    nominal_setpoint_max: float | None = None
    operating_mode: str | None = None
    eco_mode_selection: str | None = None
    dhw_charging_priority: str | None = None
    legionella_function_setpoint: float | None = None
    legionella_function_periodicity: str | None = None
    legionella_function_day: str | None = None
    legionella_function_time: str | None = None
    legionella_function_dwelling_time: float | None = None
    operating_mode_changeover: str | None = None


class State(BaseModel):
    """Object that holds information about the state of a climate system.

    All fields are optional to support partial fetching via the include
    parameter. When using state() without include, all required parameters
    will be populated.
    """

    hvac_mode: EntityInfo[int] | None = None
    target_temperature: EntityInfo[float] | None = None
    target_temperature_high: EntityInfo[float] | None = None
    hvac_action: EntityInfo[int] | None = None
    hvac_mode_changeover: EntityInfo[int] | None = None
    # 901/1201: cooling circuit operating mode
    # (0=Protection, 1=Automatic, 2=Reduced, 3=Comfort)
    cooling_operating_mode: EntityInfo[int] | None = None
    current_temperature: EntityInfo[float] | None = None
    # 8741/8771: room setpoint currently applied by the controller
    current_setpoint: EntityInfo[float] | None = None
    room1_temp_setpoint_boost: EntityInfo[float] | None = None


class StaticState(BaseModel):
    """Class for entities that are not changing."""

    # 712/1012: room temperature reduced (eco/night) setpoint
    temp_reduced_setpoint: EntityInfo[float] | None = None
    # PPS-only lower bound (15006)
    min_temp: EntityInfo[float] | None = None
    # 716/1016: comfort setpoint max upper bound
    comfort_setpoint_max: EntityInfo[float] | None = None
    # PPS-only upper bound (15007)
    max_temp: EntityInfo[float] | None = None
    # 714/1014: frost-protection lower bound
    heating_protective_setpoint: EntityInfo[float] | None = None
    cooling_comfort_setpoint_min: EntityInfo[float] | None = None
    cooling_reduced_setpoint: EntityInfo[float] | None = None


class Sensor(BaseModel):
    """Object holds info about object for sensor climate."""

    outside_temperature: EntityInfo[float] | None = None
    current_temperature: EntityInfo[float] | None = None
    total_energy: EntityInfo[int] | None = None


class HotWaterState(BaseModel):
    """Essential hot water state information (READ from device).

    This class contains only the most important hot water parameters
    that are typically checked frequently for monitoring purposes.

    Note:
        This is for READING from the device. For WRITING parameters,
        use SetHotWaterParam with set_hot_water().

    """

    operating_mode: EntityInfo[int] | None = None
    nominal_setpoint: EntityInfo[float] | None = None
    release: EntityInfo[int] | None = None
    dhw_actual_value_top_temperature: EntityInfo[float] | None = None
    dhw_current_setpoint: EntityInfo[float] | None = None
    state_dhw_pump: EntityInfo[int] | None = None


class HotWaterConfig(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Hot water configuration and advanced settings (READ from device).

    This class contains configuration parameters that are typically
    set once and checked less frequently.

    Note:
        This is for READING from the device. For WRITING parameters,
        use SetHotWaterParam with set_hot_water().

    """

    eco_mode_selection: EntityInfo[int] | None = None
    nominal_setpoint_max: EntityInfo[float] | None = None
    reduced_setpoint: EntityInfo[float] | None = None
    dhw_charging_priority: EntityInfo[int] | None = None
    operating_mode_changeover: EntityInfo[int] | None = None
    # Legionella protection settings
    legionella_function: EntityInfo[int] | None = None
    legionella_function_setpoint: EntityInfo[float] | None = None
    legionella_function_periodicity: EntityInfo[int] | None = None
    legionella_function_day: EntityInfo[int] | None = None
    legionella_function_time: EntityInfo[time] | None = None
    legionella_function_dwelling_time: EntityInfo[float] | None = None
    legionella_circulation_pump: EntityInfo[int] | None = None
    legionella_circulation_temp_diff: EntityInfo[float] | None = None
    # DHW circulation pump settings
    dhw_circulation_pump_release: EntityInfo[int] | None = None
    dhw_circulation_pump_cycling: EntityInfo[int] | None = None
    dhw_circulation_setpoint: EntityInfo[float] | None = None


class DeviceTime(BaseModel):
    """Object holds device time information."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    time: EntityInfo[str]


class Device(BaseModel):
    """Object holds bsblan device information."""

    name: str
    version: str
    MAC: str  # pylint: disable=invalid-name
    uptime: int
    bus: str | None = None
    buswritable: int | bool | None = None
    busaddr: int | None = None
    busdest: int | None = None
    busdevices: list[Any] | None = None

    @property
    def is_pps_bus(self) -> bool:
        """Return whether the device is connected to a PPS bus."""
        return self.bus is not None and self.bus.upper() == "PPS"

    @property
    def is_bus_writable(self) -> bool:
        """Return whether BSB-LAN reports global bus writes as enabled."""
        return self.buswritable is None or bool(self.buswritable)

    @property
    def supports_time_sync(self) -> bool:
        """Return whether normal BSB/LPB time synchronization is supported."""
        return not self.is_pps_bus


class ApiVersion(BaseModel):
    """Object holding the BSB-LAN JSON-API version reported by /JV.

    This is the JSON-API version (e.g. ``"2.0"``), which is distinct from the
    adapter firmware version reported by /JI. It is the documented,
    firmware-independent signal used to select a compatible API configuration.
    """

    api_version: str


class Info(BaseModel):
    """Object holding the heatingSystem info.

    All fields are optional to support partial fetching via the include
    parameter.
    """

    device_identification: EntityInfo[str] | None = None
    controller_family: EntityInfo[int] | None = None
    controller_variant: EntityInfo[int] | None = None
