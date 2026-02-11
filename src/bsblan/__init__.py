"""Asynchronous Python client for BSBLAN."""

from .bsblan import BSBLAN, BSBLANConfig
from .constants import (
    UNIT_DEVICE_CLASS_MAP,
    UNIT_STATE_CLASS_MAP,
    HeatingCircuitStatus,
    HVACActionCategory,
    get_hvac_action_category,
)
from .exceptions import BSBLANAuthError, BSBLANConnectionError, BSBLANError
from .models import (
    DaySchedule,
    Device,
    DeviceTime,
    DHWSchedule,
    DHWTimeSwitchPrograms,
    EntityInfo,
    HotWaterConfig,
    HotWaterSchedule,
    HotWaterState,
    Info,
    Sensor,
    SetHotWaterParam,
    State,
    StaticState,
    TimeSlot,
)

__all__ = [
    "BSBLAN",
    "UNIT_DEVICE_CLASS_MAP",
    "UNIT_STATE_CLASS_MAP",
    "BSBLANAuthError",
    "BSBLANConfig",
    "BSBLANConnectionError",
    "BSBLANError",
    "DHWSchedule",
    "DHWTimeSwitchPrograms",
    "DaySchedule",
    "Device",
    "DeviceTime",
    "EntityInfo",
    "HVACActionCategory",
    "HeatingCircuitStatus",
    "HotWaterConfig",
    "HotWaterSchedule",
    "HotWaterState",
    "Info",
    "Sensor",
    "SetHotWaterParam",
    "State",
    "StaticState",
    "TimeSlot",
    "get_hvac_action_category",
]
