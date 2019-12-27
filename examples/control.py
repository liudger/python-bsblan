# pylint: disable=W0621
"""Asynchronous Python client for BSBLan."""

import asyncio

from bsblan import BSBLan, State


async def main(loop):
    """Show example on controlling your BSBLan device."""
    async with BSBLan('10.0.1.60', loop=loop) as bsblan:
        state: State = await bsblan.state()
        print(state)

        thermostat = await bsblan.thermostat(target_temperature=19.0)
        # await asyncio.
        print(thermostat)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
