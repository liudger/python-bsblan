"""Fetch one or more BSB-LAN parameters and print the raw API response.

Usage:
    export BSBLAN_HOST=10.0.2.60
    export BSBLAN_PASSKEY=your_passkey  # if needed

    # Single parameter
    cd examples && python fetch_param.py 3113

    # Multiple parameters
    cd examples && python fetch_param.py 3113 8700 8740
"""

from __future__ import annotations

import argparse
import asyncio
import json

from bsblan import BSBLAN, BSBLANConfig
from discovery import get_bsblan_host, get_config_from_env


async def fetch_parameters(param_ids: list[str]) -> None:
    """Fetch and print raw API response for the given parameter IDs.

    Args:
        param_ids: List of BSB-LAN parameter IDs to fetch.

    """
    host, port = await get_bsblan_host()
    env = get_config_from_env()

    config = BSBLANConfig(
        host=host,
        port=port,
        passkey=env.get("passkey") or None,
        username=env.get("username") or None,
        password=env.get("password") or None,
    )

    params_string = ",".join(param_ids)

    async with BSBLAN(config) as client:
        result = await client._request(  # noqa: SLF001
            params={"Parameter": params_string},
        )
        print(f"Raw API response for parameter(s) {params_string}:")
        print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    """Parse arguments and run the fetch."""
    parser = argparse.ArgumentParser(
        description="Fetch BSB-LAN parameters and print raw JSON response.",
    )
    parser.add_argument(
        "params",
        nargs="+",
        help="One or more BSB-LAN parameter IDs (e.g. 3113 8700)",
    )
    args = parser.parse_args()
    asyncio.run(fetch_parameters(args.params))


if __name__ == "__main__":
    main()
