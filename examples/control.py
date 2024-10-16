# pylint: disable=W0621
"""Asynchronous Python client for BSBLan."""
import asyncio
import os

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


async def print_state(state: State) -> None:
    """Print the current state of the BSBLan device."""
    print(f"HVAC Action: {state.hvac_action.desc}")
    print(f"HVAC Mode: {state.hvac_mode.desc}")
    print(f"Current Temperature: {state.current_temperature.value}")
    print(f"boost setpoint: {state.room1_temp_setpoint_boost.value}")


async def print_sensor(sensor: Sensor) -> None:
    """Print sensor information from the BSBLan device."""
    print(f"Outside Temperature: {sensor.outside_temperature.value}")


async def print_device_info(device: Device, info: Info) -> None:
    """Print device and general information."""
    print(f"Device Name: {device.name}")
    print(f"Version: {device.version}")
    print(f"Device Identification: {info.device_identification.value}")


async def print_static_state(static_state: StaticState) -> None:
    """Print static state information."""
    print(f"Min Temperature: {static_state.min_temp.value}")
    print(f"Max Temperature: {static_state.max_temp.value}")
    print(f"Min Temperature Unit: {static_state.min_temp.unit}")


async def print_hot_water_state(hot_water_state: HotWaterState) -> None:
    """Print hot water state information."""
    print("\nHot Water State:")
    print(f"Operating Mode: {hot_water_state.operating_mode.desc}")
    print(f"Nominal Setpoint: {hot_water_state.nominal_setpoint.value}")
    print(f"Reduced Setpoint: {hot_water_state.reduced_setpoint.value}")
    print(f"Release: {hot_water_state.release.desc}")
    print(f"Legionella Function: {hot_water_state.legionella_function.desc}")
    print(f"Legionella Periodically: {hot_water_state.legionella_periodically.value}")
    print(f"Legionella Setpoint: {hot_water_state.legionella_setpoint.value}")


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


if __name__ == "__main__":
    asyncio.run(main())
