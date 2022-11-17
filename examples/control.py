# pylint: disable=W0621
"""Asynchronous Python client for BSBLan."""

import asyncio

from bsblan import BSBLAN, Device, Info, Sensor, State
from bsblan.models import StaticState


async def main():
    """Show example on controlling your BSBLan device.

    Options:
    - passkey (http://url/"passkey"/) if your device is setup for passkey authentication
    - username and password if your device is setup for username/password authentication

    """
    async with BSBLAN(
        host="10.0.2.60",
        passkey=None,
        username=None,
        password=None,
    ) as bsblan:
        # get state from bsblan device
        state: State = await bsblan.state()
        # state give all the parameters needed for climate device
        print(f"hvac_action: {state.hvac_action.desc}")
        print(f"hvac_mode: {state.hvac_mode.desc}")
        print(f"current temperature: {state.current_temperature.value}")

        # set temp thermostat
        print("Setting temperature to 18.5")
        await bsblan.thermostat(target_temperature="18.5")
        # set hvac_mode (0-3) (protection,auto,reduced,comfort)
        await bsblan.thermostat(hvac_mode="heat")

        # get sensor from bsblan device
        sensor: Sensor = await bsblan.sensor()
        print(f"outside temperature: {sensor.outside_temperature.value}")

        # get some generic info from the heater
        device: Device = await bsblan.device()
        print(f"device dict: {device.dict()}")
        print(f"device: {device.name}")
        print(f"version: {device.version}")

        info: Info = await bsblan.info()
        print(f"device: {info.device_identification.dict()}")
        print(f"name: {info.device_identification.value}")

        static_state: StaticState = await bsblan.static_values()
        print(f"min temp: {static_state.min_temp.value}")
        print(f"max temp: {static_state.max_temp.value}")


if __name__ == "__main__":
    loop = asyncio.get_event_loop_policy().get_event_loop()
    loop.run_until_complete(main())
