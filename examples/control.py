# pylint: disable=W0621
"""Asynchronous Python client for BSBLan."""

import asyncio

from bsblan import BSBLan, Info, State


async def main():
    """Show example on controlling your BSBLan device.

    Options:
    - passkey (http://url/"passkey"/) if your device is setup for passkey authentication
    - username and password if your device is setup for username/password authentication

    """
    async with BSBLan(
        host="10.0.1.60", passkey=None, username=None, password=None,
    ) as bsblan:
        # get state from bsblan device
        state: State = await bsblan.state()
        print(state)

        # set temp thermostat
        await bsblan.thermostat(target_temperature=18.5)

        # set hvac_mode (0-3) (protection,auto,reduced,comfort)
        await bsblan.thermostat(hvac_mode=3)

        # get some generic info from the heater
        info: Info = await bsblan.info()
        print(info)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
