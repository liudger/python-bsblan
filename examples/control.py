# pylint: disable=W0621
"""Asynchronous Python client for BSBLan."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from bsblan import (
    BSBLAN,
    BSBLANConfig,
    Device,
    HotWaterState,
    Info,
    Sensor,
    State,
    StaticState,
)
from bsblan.models import DHWTimeSwitchPrograms


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


async def print_state(state: State) -> None:
    """Print the current state of the BSBLan device.

    Args:
        state (State): The current state of the BSBLan device.

    """
    attributes = {
        "HVAC Action": await get_attribute(state.hvac_action, "desc", "Unknown Action"),
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
    """Print hot water state information.

    Args:
        hot_water_state (HotWaterState): The hot water state information from the
            BSBLan device.

    """
    attributes = {
        "Operating Mode": await get_attribute(
            hot_water_state.operating_mode, "desc", "Unknown Mode"
        ),
        "Nominal Setpoint": await get_attribute(
            hot_water_state.nominal_setpoint, "value", "N/A"
        ),
        "Reduced Setpoint": await get_attribute(
            hot_water_state.reduced_setpoint, "value", "N/A"
        ),
        "Release": await get_attribute(hot_water_state.release, "desc", "N/A"),
        "Legionella Function": await get_attribute(
            hot_water_state.legionella_function, "desc", "N/A"
        ),
        "Legionella Periodicity": await get_attribute(
            hot_water_state.legionella_periodicity, "value", "N/A"
        ),
        "Legionella Setpoint": await get_attribute(
            hot_water_state.legionella_setpoint, "value", "N/A"
        ),
        "Current Temperature": await get_attribute(
            hot_water_state.dhw_actual_value_top_temperature, "value", "N/A"
        ),
        "Time Program Monday": await get_attribute(
            hot_water_state.dhw_time_program_monday, "value", "N/A"
        ),
        "Time Program Tuesday": await get_attribute(
            hot_water_state.dhw_time_program_tuesday, "value", "N/A"
        ),
        "Time Program Wednesday": await get_attribute(
            hot_water_state.dhw_time_program_wednesday, "value", "N/A"
        ),
        "Time Program Thursday": await get_attribute(
            hot_water_state.dhw_time_program_thursday, "value", "N/A"
        ),
        "Time Program Friday": await get_attribute(
            hot_water_state.dhw_time_program_friday, "value", "N/A"
        ),
        "Time Program Saturday": await get_attribute(
            hot_water_state.dhw_time_program_saturday, "value", "N/A"
        ),
        "Time Program Sunday": await get_attribute(
            hot_water_state.dhw_time_program_sunday, "value", "N/A"
        ),
    }
    print_attributes("Hot Water State", attributes)


async def main() -> None:
    """Show example on controlling your BSBLan device."""
    # Create a configuration object
    config = BSBLANConfig(
        host="10.0.2.60",
        passkey=None,
        username=os.getenv("BSBLAN_USER"),  # Compliant
        password=os.getenv("BSBLAN_PASS"),  # Compliant
    )

    # Initialize BSBLAN with the configuration object
    async with BSBLAN(config) as bsblan:
        # Get and print state
        state: State = await bsblan.state()
        await print_state(state)

        # Set thermostat temperature
        print("\nSetting temperature to 18°C")
        await bsblan.thermostat(target_temperature="18")

        # Set HVAC mode
        print("Setting HVAC mode to heat")
        await bsblan.thermostat(hvac_mode="heat")

        # Get and print sensor information
        sensor: Sensor = await bsblan.sensor()
        await print_sensor(sensor)

        # Get and print device and general info
        device: Device = await bsblan.device()
        info: Info = await bsblan.info()
        await print_device_info(device, info)

        # Get and print static state
        static_state: StaticState = await bsblan.static_values()
        await print_static_state(static_state)

        # Get hot water state
        hot_water_state: HotWaterState = await bsblan.hot_water_state()
        await print_hot_water_state(hot_water_state)

        # Example: Set DHW time program for Monday
        print("\nSetting DHW time program for Monday to 13:00-14:00")

        dhw_programs = DHWTimeSwitchPrograms(
            monday="13:00-14:00 ##:##-##:## ##:##-##:##"
        )
        await bsblan.set_hot_water(dhw_time_programs=dhw_programs)


if __name__ == "__main__":
    asyncio.run(main())
