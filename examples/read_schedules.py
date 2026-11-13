"""Read schedules without writes, using independently confirmed weekday mappings.

Set BSBLAN_HOST (or use discovery), then supply one or both seven-day mappings
as JSON. No default profile is assumed. The control example is not read-only.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import cast

from bsblan import BSBLAN, BSBLANConfig, ScheduleMapping, ScheduleMappings
from discovery import get_bsblan_host, get_config_from_env


def parse_mappings(argv: list[str] | None = None) -> ScheduleMappings:
    """Validate complete mappings before discovery or any device request."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hot-water-mapping",
        type=ScheduleMapping.model_validate_json,
        help="JSON object of independently confirmed weekday string IDs for DHW.",
    )
    parser.add_argument(
        "--heating-mapping",
        type=ScheduleMapping.model_validate_json,
        help="JSON object of independently confirmed weekday string IDs for heating.",
    )
    parser.add_argument("--circuit", type=int, choices=(1, 2), default=1)
    args = parser.parse_args(argv)
    if args.hot_water_mapping is None and args.heating_mapping is None:
        parser.error("At least one confirmed schedule mapping is required.")
    return ScheduleMappings(
        hot_water=args.hot_water_mapping,
        **{f"heating_{args.circuit}": args.heating_mapping},
    )


async def main(mappings: ScheduleMappings) -> None:
    """Print JSON observations for configured groups only, never write them."""
    host, port = await get_bsblan_host()
    env = get_config_from_env()
    config = BSBLANConfig(
        host=host,
        port=port,
        username=cast("str | None", env.get("username")),
        password=cast("str | None", env.get("password")),
        passkey=cast("str | None", env.get("passkey")),
        schedule_mappings=mappings,
    )
    async with BSBLAN(config) as client:
        if mappings.hot_water is not None:
            snapshot = await client.hot_water_schedule()
            print(snapshot.model_dump_json(indent=2))
        for circuit in (1, 2):
            if getattr(mappings, f"heating_{circuit}") is not None:
                snapshot = await client.heating_schedule(circuit=circuit)
                print(snapshot.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main(parse_mappings()))
