"""Fetch BSB-LAN parameters and print the raw API response.

Uses BSB-LAN's URL commands (https://docs.bsb-lan.de/using.html):

- ``/JQ`` (default): query current parameter values.
- ``/JC`` (``--structure``): dump the parameter structure, including data
  type, read/write flag, unit, and enum ``possibleValues``. Useful for
  verifying that a parameter ID is correct and learning its valid options.
- ``/JK`` (``--category``): dump every parameter in a category.

Usage:
    export BSBLAN_HOST=192.0.2.1
    export BSBLAN_PASSKEY=your_passkey  # if needed

    # Single parameter (current value)
    cd examples && python fetch_param.py 3113

    # Multiple parameters
    cd examples && python fetch_param.py 3113 8700 8740

    # Parameter structure (type, unit, read/write, enum options)
    cd examples && python fetch_param.py --structure 700 902

    # All parameters of a category (e.g. category 1)
    cd examples && python fetch_param.py --category 1
"""

from __future__ import annotations

import argparse
import asyncio
import json

from bsblan import BSBLAN, BSBLANConfig
from discovery import get_bsblan_host, get_config_from_env


async def _build_client() -> BSBLAN:
    """Create a configured BSBLAN client from env/mDNS discovery.

    Returns:
        A BSBLAN client to use as an async context manager.

    """
    host, port = await get_bsblan_host()
    env = get_config_from_env()

    config = BSBLANConfig(
        host=host,
        port=port,
        passkey=str(env["passkey"]) if env.get("passkey") else None,
        username=str(env["username"]) if env.get("username") else None,
        password=str(env["password"]) if env.get("password") else None,
    )
    return BSBLAN(config)


def _print_result(label: str, result: dict[str, object]) -> None:
    """Pretty-print a raw API response."""
    print(label)
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def fetch_values(param_ids: list[str]) -> None:
    """Fetch and print current values for the given parameter IDs (/JQ).

    Args:
        param_ids: List of BSB-LAN parameter IDs to fetch.

    """
    params_string = ",".join(param_ids)
    client = await _build_client()
    async with client:
        result = await client._request(  # noqa: SLF001
            params={"Parameter": params_string},
        )
        _print_result(f"Values for parameter(s) {params_string}:", result)


async def fetch_structure(param_ids: list[str]) -> None:
    """Fetch and print the parameter structure for the given IDs (/JC).

    Shows data type, read/write flag, unit and enum ``possibleValues``.

    Args:
        param_ids: List of BSB-LAN parameter IDs to inspect.

    """
    params_string = ",".join(param_ids)
    client = await _build_client()
    async with client:
        result = await client._request(  # noqa: SLF001
            method="GET",
            base_path=f"/JC={params_string}",
            params=None,
        )
        _print_result(f"Structure for parameter(s) {params_string}:", result)


async def fetch_category(category: str) -> None:
    """Fetch and print every parameter of a category (/JK).

    Args:
        category: The BSB-LAN category ID to dump.

    """
    client = await _build_client()
    async with client:
        result = await client._request(  # noqa: SLF001
            method="GET",
            base_path=f"/JK={category}",
            params=None,
        )
        _print_result(f"Parameters in category {category}:", result)


def main() -> None:
    """Parse arguments and run the requested query."""
    parser = argparse.ArgumentParser(
        description=(
            "Fetch BSB-LAN parameters and print the raw JSON response. "
            "Defaults to current values (/JQ); use --structure (/JC) or "
            "--category (/JK) for metadata."
        ),
    )
    parser.add_argument(
        "params",
        nargs="*",
        help="One or more BSB-LAN parameter IDs (e.g. 3113 8700)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "-s",
        "--structure",
        action="store_true",
        help=(
            "Dump parameter structure (data type, unit, read/write, enum "
            "options) via /JC instead of current values."
        ),
    )
    mode.add_argument(
        "-c",
        "--category",
        metavar="ID",
        help="Dump all parameters of the given category ID via /JK.",
    )
    args = parser.parse_args()

    if args.category is not None:
        if args.params:
            parser.error("--category cannot be combined with parameter IDs")
        asyncio.run(fetch_category(args.category))
        return

    if not args.params:
        parser.error("at least one parameter ID is required")

    if args.structure:
        asyncio.run(fetch_structure(args.params))
    else:
        asyncio.run(fetch_values(args.params))


if __name__ == "__main__":
    main()
