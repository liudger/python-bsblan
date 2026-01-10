# pylint: disable=W0621
"""Asynchronous Python client for BSBLan.

This example demonstrates the optimized hot water functionality:
- HotWaterState: Essential parameters for frequent polling (5 fields)
- HotWaterConfig: Configuration parameters checked less frequently (16 fields)
- HotWaterSchedule: Time program schedules checked occasionally (8 fields)

This three-tier approach reduces API calls by 79% for regular monitoring.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from bsblan import (
    BSBLAN,
    BSBLANConfig,
    Device,
    DeviceTime,
    HeatingCircuitStatus,
    HotWaterConfig,
    HotWaterSchedule,
    HotWaterState,
    Info,
    Sensor,
    SetHotWaterParam,
    State,
    StaticState,
    get_hvac_action_category,
)
from bsblan.models import DHWTimeSwitchPrograms
from discovery import get_bsblan_host, get_config_from_env


async def get_attribute(
    attribute: Any, attr_type: str = "value", default: str = "N/A"
) -> str:
    """Safely retrieve the desired property ('value' or 'desc') of an attribute.

    Args:
        attribute: The attribute object which may have 'value' or 'desc'.
        attr_type (str): The type of attribute to retrieve ('value' or 'desc').
        default (str): The default value to return if the attribute is None.

    Returns:
        str: The retrieved attribute value or the default.

    """
    if attribute is None:
        return default
    return getattr(attribute, attr_type, default)


def print_attributes(title: str, attributes: dict[str, str]) -> None:
    """Print a set of attributes with their labels under a given title.

    Args:
        title (str): The title for the group of attributes.
        attributes (dict): A dictionary where keys are labels and values are
            attribute values.

    """
    print(f"\n{title}:")
    for label, value in attributes.items():
        print(f"{label}: {value}")


def get_hvac_action_name(status_code: int) -> str:
    """Map BSB-LAN parameter 8000 status code to a human-readable HVAC action.

    BSB-LAN parameter 8000 ("Status heating circuit 1") returns vendor-specific
    status codes. This function maps those codes to simplified HVAC action states
    compatible with Home Assistant and other automation systems.

    Args:
        status_code: The raw status code from parameter 8000 (hvac_action.value).

    Returns:
        str: Human-readable HVAC action name. Returns "idle" for unmapped codes.

    Example:
        >>> state = await bsblan.state()
        >>> if state.hvac_action is not None:
        ...     action = get_hvac_action_name(state.hvac_action.value)
        ...     print(f"Current HVAC action: {action}")

    """
    # Use the new enum-based approach
    category = get_hvac_action_category(status_code)
    return category.name.lower()


async def print_state(state: State) -> None:
    """Print the current state of the BSBLan device.

    Args:
        state (State): The current state of the BSBLan device.

    """
    # Get the HVAC action - both the raw value and mapped action name
    hvac_action_desc = await get_attribute(state.hvac_action, "desc", "Unknown Action")
    hvac_action_value = await get_attribute(state.hvac_action, "value", "N/A")

    # Map the raw status code to a simplified action name using the new enum approach
    hvac_action_mapped = "N/A"
    status_name = "N/A"
    if hvac_action_value != "N/A":
        try:
            status_code = int(hvac_action_value)
            # Get the category (heating, cooling, etc.)
            hvac_action_mapped = get_hvac_action_name(status_code)
            # Get the specific status name from the enum (if known)
            status = HeatingCircuitStatus.from_value(status_code)
            status_name = status.name if status else "UNKNOWN"
        except (ValueError, TypeError):
            hvac_action_mapped = "unknown"

    attributes = {
        "HVAC Action (raw value)": str(hvac_action_value),
        "HVAC Action (device desc)": hvac_action_desc,
        "HVAC Action (status name)": status_name,
        "HVAC Action (category)": hvac_action_mapped,
        "HVAC Mode": await get_attribute(state.hvac_mode, "desc", "Unknown Mode"),
        "Current Temperature": await get_attribute(
            state.current_temperature, "value", "N/A"
        ),
    }
    print_attributes("Device State", attributes)


async def print_sensor(sensor: Sensor) -> None:
    """Print sensor information from the BSBLan device.

    Args:
        sensor (Sensor): The sensor information from the BSBLan device.

    """
    attributes = {
        "Outside Temperature": await get_attribute(
            sensor.outside_temperature, "value", "N/A"
        ),
        "Current Temperature": await get_attribute(
            sensor.current_temperature, "value", "N/A"
        ),
    }
    print_attributes("Sensor Information", attributes)


async def print_device_time(device_time: DeviceTime) -> None:
    """Print device time information.

    Args:
        device_time (DeviceTime): The device time information from the BSBLan device.

    """
    attributes = {
        "Current Time": await get_attribute(device_time.time, "value", "N/A"),
        "Time Unit": await get_attribute(device_time.time, "unit", "N/A"),
        "Time Description": await get_attribute(device_time.time, "desc", "N/A"),
    }
    print_attributes("Device Time", attributes)


async def print_device_info(device: Device, info: Info) -> None:
    """Print device and general information.

    Args:
        device (Device): The device information from the BSBLan device.
        info (Info): The general information from the BSBLan device.

    """
    device_identification = await get_attribute(
        info.device_identification, "value", "N/A"
    )

    attributes = {
        "Device Name": device.name if device.name else "N/A",
        "Version": device.version if device.version else "N/A",
        "Device Identification": device_identification,
    }
    print_attributes("Device Information", attributes)


async def print_static_state(static_state: StaticState) -> None:
    """Print static state information.

    Args:
        static_state (StaticState): The static state information from the BSBLan device.

    """
    min_temp = await get_attribute(static_state.min_temp, "value", "N/A")
    max_temp = await get_attribute(static_state.max_temp, "value", "N/A")
    min_temp_unit = await get_attribute(static_state.min_temp, "unit", "N/A")

    attributes = {
        "Min Temperature": min_temp,
        "Max Temperature": max_temp,
        "Min Temperature Unit": min_temp_unit,
    }
    print_attributes("Static State", attributes)


async def print_hot_water_state(hot_water_state: HotWaterState) -> None:
    """Print essential hot water state information.

    Args:
        hot_water_state (HotWaterState): The essential hot water state information
            from the BSBLan device (optimized for frequent polling).

    """
    attributes = {
        "Operating Mode": await get_attribute(
            hot_water_state.operating_mode, "desc", "Unknown Mode"
        ),
        "Nominal Setpoint": await get_attribute(
            hot_water_state.nominal_setpoint, "value", "N/A"
        ),
        "Release": await get_attribute(hot_water_state.release, "desc", "N/A"),
        "Current Temperature": await get_attribute(
            hot_water_state.dhw_actual_value_top_temperature, "value", "N/A"
        ),
        "DHW Pump State": await get_attribute(
            hot_water_state.state_dhw_pump, "desc", "N/A"
        ),
    }
    print_attributes("Hot Water State (Essential)", attributes)


async def print_hot_water_config(hot_water_config: HotWaterConfig) -> None:
    """Print hot water configuration information.

    Args:
        hot_water_config (HotWaterConfig): The hot water configuration information
            from the BSBLan device (checked less frequently).

    """
    attributes = {
        "Nominal Setpoint Max": await get_attribute(
            hot_water_config.nominal_setpoint_max, "value", "N/A"
        ),
        "Reduced Setpoint": await get_attribute(
            hot_water_config.reduced_setpoint, "value", "N/A"
        ),
        "Legionella Function": await get_attribute(
            hot_water_config.legionella_function, "desc", "N/A"
        ),
        "Legionella Setpoint": await get_attribute(
            hot_water_config.legionella_function_setpoint, "value", "N/A"
        ),
        "Legionella Periodicity": await get_attribute(
            hot_water_config.legionella_function_periodicity, "value", "N/A"
        ),
        "Circulation Pump Release": await get_attribute(
            hot_water_config.dhw_circulation_pump_release, "desc", "N/A"
        ),
        "Circulation Setpoint": await get_attribute(
            hot_water_config.dhw_circulation_setpoint, "value", "N/A"
        ),
    }
    print_attributes("Hot Water Configuration", attributes)


async def print_hot_water_schedule(hot_water_schedule: HotWaterSchedule) -> None:
    """Print hot water schedule information.

    Args:
        hot_water_schedule (HotWaterSchedule): The hot water schedule information
            from the BSBLan device (time programs).

    """
    attributes = {
        "Monday": await get_attribute(
            hot_water_schedule.dhw_time_program_monday, "value", "N/A"
        ),
        "Tuesday": await get_attribute(
            hot_water_schedule.dhw_time_program_tuesday, "value", "N/A"
        ),
        "Wednesday": await get_attribute(
            hot_water_schedule.dhw_time_program_wednesday, "value", "N/A"
        ),
        "Thursday": await get_attribute(
            hot_water_schedule.dhw_time_program_thursday, "value", "N/A"
        ),
        "Friday": await get_attribute(
            hot_water_schedule.dhw_time_program_friday, "value", "N/A"
        ),
        "Saturday": await get_attribute(
            hot_water_schedule.dhw_time_program_saturday, "value", "N/A"
        ),
        "Sunday": await get_attribute(
            hot_water_schedule.dhw_time_program_sunday, "value", "N/A"
        ),
        "Standard Values": await get_attribute(
            hot_water_schedule.dhw_time_program_standard_values, "value", "N/A"
        ),
    }
    print_attributes("Hot Water Schedule", attributes)


async def main() -> None:
    """Show example on controlling your BSBLan device."""
    # Get host from environment variable or mDNS discovery
    host, port = await get_bsblan_host()

    # Get credentials from environment
    env_config = get_config_from_env()

    # Create a configuration object
    config = BSBLANConfig(
        host=host,
        port=port,
        passkey=env_config.get("passkey"),  # type: ignore[arg-type]
        username=env_config.get("username"),  # type: ignore[arg-type]
        password=env_config.get("password"),  # type: ignore[arg-type]
    )

    # Initialize BSBLAN with the configuration object
    async with BSBLAN(config) as bsblan:
        # Get and print state
        state: State = await bsblan.state()
        await print_state(state)

        # Set thermostat temperature
        print("\nSetting temperature to 18°C")
        await bsblan.thermostat(target_temperature="18")

        # Set HVAC mode (using raw integer: 0=off, 1=auto, 2=eco, 3=heat)
        print("Setting HVAC mode to heat")
        await bsblan.thermostat(hvac_mode=3)  # 3 = heat

        # Get and print sensor information
        sensor: Sensor = await bsblan.sensor()
        await print_sensor(sensor)

        # Get and print device and general info
        device: Device = await bsblan.device()
        info: Info = await bsblan.info()
        await print_device_info(device, info)

        # Get and print device time
        device_time: DeviceTime = await bsblan.time()
        await print_device_time(device_time)

        # Get and print static state
        static_state: StaticState = await bsblan.static_values()
        await print_static_state(static_state)

        # Get hot water state (essential parameters for frequent polling)
        hot_water_state: HotWaterState = await bsblan.hot_water_state()
        await print_hot_water_state(hot_water_state)

        # Get hot water configuration (checked less frequently)
        try:
            hot_water_config: HotWaterConfig = await bsblan.hot_water_config()
            await print_hot_water_config(hot_water_config)
        except Exception as e:  # noqa: BLE001 - Broad exception for demo purposes
            print(f"Hot water configuration not available: {e}")

        # Get hot water schedule (time programs)
        try:
            hot_water_schedule: HotWaterSchedule = await bsblan.hot_water_schedule()
            await print_hot_water_schedule(hot_water_schedule)
        except Exception as e:  # noqa: BLE001 - Broad exception for demo purposes
            print(f"Hot water schedule not available: {e}")

        # Example: Set DHW time program for Monday
        print("\nSetting DHW time program for Monday to 13:00-14:00")

        dhw_programs = DHWTimeSwitchPrograms(
            monday="13:00-14:00 ##:##-##:## ##:##-##:##"
        )
        await bsblan.set_hot_water(SetHotWaterParam(dhw_time_programs=dhw_programs))

        # Example: Set device time
        print("\nSetting device time to current system time")
        # Get current local system time and format it for BSB-LAN (DD.MM.YYYY HH:MM:SS)
        # Note: Using local time intentionally for this demo to sync BSB-LAN
        current_time = datetime.now().replace(microsecond=0)  # noqa: DTZ005 - Demo uses local time
        formatted_time = current_time.strftime("%d.%m.%Y %H:%M:%S")
        print(f"Current system time: {formatted_time}")
        await bsblan.set_time(formatted_time)


if __name__ == "__main__":
    asyncio.run(main())
