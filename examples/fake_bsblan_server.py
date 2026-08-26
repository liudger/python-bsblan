"""Fake BSB-LAN server for testing multi-circuit config flows.

Simulates a BSB-LAN device with 2 (or 3) heating circuits.
All three endpoints (/JQ, /JI, /JS) are implemented.

Usage:
    python script/fake_bsblan_server.py [--port 8080] [--circuits 2] [--passkey KEY]
        [--omit-static-values] [--omit-dhw]
        [--json-api-version 2.0 | --json-api-version 1.0]
        [--json-api-unavailable]

Options:
    --omit-static-values  Omit heating circuit min/max temperature parameters
                          from responses, simulating devices that don't support
                          static values.
    --omit-dhw            Omit all DHW (Domestic Hot Water) parameters from
                          responses, simulating devices without hot water support.
    --firmware-version    Override the reported firmware version. Use a v1
                          version (e.g. 1.0.0) to trigger the outdated firmware
                          repair issue.
    --json-api-version    Value returned by /JV as the JSON-API version
                          (default: 2.0).
    --json-api-unavailable Simulate a device where /JV cannot be retrieved.
                          The endpoint will return HTTP 404.

Then add the integration in Home Assistant UI with:
    Host: 127.0.0.1  (or localhost)
    Port: 8080        (or whatever you set)
    Passkey: (leave blank unless --passkey was set)

The config flow should detect multiple circuits and show the selection step.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_LOGGER = logging.getLogger("fake_bsblan")

# ---------------------------------------------------------------------------
# Device identity
# ---------------------------------------------------------------------------
DEVICE_INFO: dict[str, Any] = {
    "name": "BSB-LAN",
    "version": "3.3.2-20250101120000",
    "freeram": 42000,
    "uptime": 123456789,
    "MAC": "00:80:41:DE:AD:01",
    "freespace": 0,
    "bus": "BSB",
    "buswritable": 1,
    "busaddr": 66,
    "busdest": 0,
    "monitor": 0,
    "verbose": 1,
    "protectedGPIO": [{"pin": 0}],
    "averages": [],
}

# ---------------------------------------------------------------------------
# Parameter database — keyed by parameter ID string
# ---------------------------------------------------------------------------


def _param(
    name: str,
    value: str,
    *,
    desc: str = "",
    data_type: int = 0,
    readonly: int = 0,
    unit: str = "",
    precision: float | None = None,
    readwrite: int = 0,
) -> dict[str, Any]:
    """Build a single parameter response entry."""
    entry: dict[str, Any] = {
        "name": name,
        "error": 0,
        "value": value,
        "desc": desc,
        "dataType": data_type,
        "readonly": readonly,
        "unit": unit,
    }
    if precision is not None:
        entry["precision"] = precision
    entry["readwrite"] = readwrite
    return entry


def _inactive_param(name: str) -> dict[str, Any]:
    """Build an inactive/unavailable parameter entry."""
    return {
        "name": name,
        "error": 0,
        "value": "0",
        "desc": "---",
        "dataType": 1,
        "readonly": 1,
        "unit": "",
    }


def build_parameter_db(
    num_circuits: int, *, omit_dhw: bool = False
) -> dict[str, dict[str, Any]]:
    """Build the full parameter database for the simulated device.

    Args:
        num_circuits: Number of active heating circuits (1, 2, or 3).
        omit_dhw: If True, omit all DHW parameters (no hot water support).

    """
    db: dict[str, dict[str, Any]] = {}

    # ---- Device info params (6224-6226) ----
    db["6224"] = _param("Device identification", "RVS21.831F/127", data_type=7)
    db["6225"] = _param("Device family", "211")
    db["6226"] = _param("Device variant", "127")

    # ---- Sensor params ----
    db["8700"] = _param("Outside temp sensor local", "6.1", unit="&deg;C", readonly=1)
    db["8740"] = _param("Room temp 1 actual value", "21.3", unit="&deg;C", readonly=1)
    db["3113"] = _param("Total energy", "7968", unit="kWh", readonly=1)

    # ---- Time param (0) ----
    db["0"] = _param("Date/time", "02.03.2026 14:00:00", data_type=5)

    # ---- Hot water params ----
    if not omit_dhw:
        db["1600"] = _param("DHW operating mode", "1", desc="On", data_type=1)
        db["1601"] = _param("DHW eco mode selection", "0", desc="Off", data_type=1)
        db["1610"] = _param("DHW nominal setpoint", "50.0", unit="&deg;C")
        db["1612"] = _param("DHW reduced setpoint", "40.0", unit="&deg;C")
        db["1614"] = _param("DHW nominal setpoint max", "65.0", unit="&deg;C")
        db["1620"] = _param("DHW release", "1", desc="Released", data_type=1)
        db["1630"] = _param(
            "DHW charging priority", "1", desc="DHW priority", data_type=1
        )
        db["1640"] = _param("Legionella function", "0", desc="Off", data_type=1)
        db["1641"] = _param("Legionella periodicity", "4", desc="4 weeks", data_type=1)
        db["1642"] = _param("Legionella day", "6", desc="Saturday", data_type=3)
        db["1644"] = _param("Legionella time", "03:00", data_type=4)
        db["1645"] = _param("Legionella setpoint", "70.0", unit="&deg;C")
        db["1646"] = _param("Legionella dwelling time", "5", unit="min")
        db["1647"] = _param("Legionella circulation pump", "1", desc="On", data_type=1)
        db["1648"] = _param("Legionella circulation temp diff", "0", unit="K")
        db["1660"] = _param(
            "DHW circulation pump release", "1", desc="24H/Day", data_type=1
        )
        db["1661"] = _param(
            "DHW circulation pump cycling", "1", desc="1x 3min/h", data_type=1
        )
        db["1663"] = _param("DHW circulation setpoint", "40.0", unit="&deg;C")
        db["1680"] = _param("DHW changeover", "0", desc="---", data_type=1)
        db["8830"] = _param("DHW actual top temp", "48.2", unit="&deg;C", readonly=1)
        db["8820"] = _param(
            "DHW pump state", "255", desc="Off", data_type=1, readonly=1
        )

        # DHW schedule params
        for pid, day in [
            ("561", "Monday"),
            ("562", "Tuesday"),
            ("563", "Wednesday"),
            ("564", "Thursday"),
            ("565", "Friday"),
            ("566", "Saturday"),
            ("567", "Sunday"),
        ]:
            db[pid] = _param(
                f"DHW time program {day}",
                "06:00-22:00 ##:##-##:## ##:##-##:##",
                data_type=9,
            )
        db["576"] = _param(
            "DHW time program standard values", "0", desc="No", data_type=1
        )

    # ---- Heating Circuit 1 (700-series) — always active ----
    db["700"] = _param("HC1 Operating mode", "3", desc="Comfort", data_type=1)
    db["710"] = _param("HC1 Room temp comfort setpoint", "21.0", unit="&deg;C")
    db["714"] = _param("HC1 Room temp frost protection", "8.0", unit="&deg;C")
    db["716"] = _param("HC1 Max temp", "26.0", unit="&deg;C")
    db["730"] = _param("HC1 Summer/winter changeover", "20.0", unit="&deg;C")
    db["770"] = _param("HC1 Room1 temp setpoint boost", "0.0", unit="&deg;C")
    db["900"] = _param("HC1 Changeover mode", "0", desc="---", data_type=1)
    db["8000"] = _param(
        "Status heating circuit 1",
        "122",
        desc="Room temp limiting",
        data_type=1,
        readonly=1,
    )
    db["8749"] = _param(
        "HC1 Room1 thermostat mode", "0", desc="No demand", data_type=1, readonly=1
    )

    # ---- Heating Circuit 2 (1000-series) ----
    if num_circuits >= 2:
        db["1000"] = _param("HC2 Operating mode", "1", desc="Auto", data_type=1)
        db["1010"] = _param("HC2 Room temp comfort setpoint", "19.0", unit="&deg;C")
        db["1014"] = _param("HC2 Room temp frost protection", "8.0", unit="&deg;C")
        db["1016"] = _param("HC2 Max temp", "24.0", unit="&deg;C")
        db["1030"] = _param("HC2 Summer/winter changeover", "20.0", unit="&deg;C")
        db["1070"] = _param("HC2 Room1 temp setpoint boost", "0.0", unit="&deg;C")
        db["1200"] = _param("HC2 Changeover mode", "0", desc="---", data_type=1)
        db["8001"] = _param(
            "Status heating circuit 2",
            "100",
            desc="Heating",
            data_type=1,
            readonly=1,
        )
        db["8741"] = _param(
            "Room temp 2 actual value", "19.8", unit="&deg;C", readonly=1
        )
        db["8750"] = _param(
            "HC2 Room1 thermostat mode",
            "1",
            desc="Comfort",
            data_type=1,
            readonly=1,
        )
    else:
        # Inactive HC2
        db["1000"] = _inactive_param("HC2 Operating mode")
        db["8001"] = _inactive_param("Status heating circuit 2")

    # ---- Heating Circuit 3 (1300-series) ----
    if num_circuits >= 3:
        db["1300"] = _param("HC3 Operating mode", "1", desc="Auto", data_type=1)
        db["1310"] = _param("HC3 Room temp comfort setpoint", "18.0", unit="&deg;C")
        db["1314"] = _param("HC3 Room temp frost protection", "8.0", unit="&deg;C")
        db["1316"] = _param("HC3 Max temp", "22.0", unit="&deg;C")
        db["1330"] = _param("HC3 Summer/winter changeover", "20.0", unit="&deg;C")
        db["1370"] = _param("HC3 Room1 temp setpoint boost", "0.0", unit="&deg;C")
        db["1500"] = _param("HC3 Changeover mode", "0", desc="---", data_type=1)
        db["8002"] = _param(
            "Status heating circuit 3",
            "100",
            desc="Heating",
            data_type=1,
            readonly=1,
        )
        db["8742"] = _param(
            "Room temp 3 actual value", "17.5", unit="&deg;C", readonly=1
        )
        db["8751"] = _param(
            "HC3 Room1 thermostat mode",
            "1",
            desc="Comfort",
            data_type=1,
            readonly=1,
        )
    else:
        db["1300"] = _inactive_param("HC3 Operating mode")
        db["8002"] = _inactive_param("Status heating circuit 3")

    return db


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------


class FakeBSBLAN:
    """Fake BSB-LAN HTTP server."""

    def __init__(
        self,
        num_circuits: int = 2,
        passkey: str | None = None,
        *,
        omit_static_values: bool = False,
        omit_dhw: bool = False,
        firmware_version: str | None = None,
        json_api_version: str = "2.0",
        json_api_unavailable: bool = False,
    ) -> None:
        """Initialize fake server."""
        self.db = build_parameter_db(num_circuits, omit_dhw=omit_dhw)
        self.passkey = passkey
        self.num_circuits = num_circuits
        self.omit_static_values = omit_static_values
        self.omit_dhw = omit_dhw
        self.json_api_version = json_api_version
        self.json_api_unavailable = json_api_unavailable
        self.device_info = dict(DEVICE_INFO)
        if firmware_version is not None:
            self.device_info["version"] = firmware_version

    @property
    def omitted_parameters(self) -> set[str]:
        """Return parameter IDs that should be omitted from responses."""
        omitted: set[str] = set()

        if self.omit_static_values:
            omitted.update({"714", "716", "1014", "1016", "1314", "1316"})

        if self.omit_dhw:
            # All DHW-related parameter IDs — omitting these causes the library
            # to raise BSBLANError, matching real devices without hot water support
            omitted.update(
                {
                    "561",
                    "562",
                    "563",
                    "564",
                    "565",
                    "566",
                    "567",
                    "576",
                    "1600",
                    "1601",
                    "1610",
                    "1612",
                    "1614",
                    "1620",
                    "1630",
                    "1640",
                    "1641",
                    "1642",
                    "1644",
                    "1645",
                    "1646",
                    "1647",
                    "1648",
                    "1660",
                    "1661",
                    "1663",
                    "1680",
                    "8820",
                    "8830",
                }
            )

        return omitted

    def _prefix(self) -> str:
        """Return URL prefix (with passkey if set)."""
        if self.passkey:
            return f"/{self.passkey}"
        return ""

    async def handle_jq(self, request: web.Request) -> web.Response:
        """Handle /JQ — query parameters."""
        param_str = request.query.get("Parameter", "")
        param_ids = [p.strip() for p in param_str.split(",") if p.strip()]

        _LOGGER.info("JQ request: params=%s (from %s)", param_ids, request.remote)

        result: dict[str, Any] = {}
        for pid in param_ids:
            if pid in self.omitted_parameters:
                _LOGGER.info("Omitting parameter %s from response", pid)
                continue
            if pid in self.db:
                result[pid] = self.db[pid]
            else:
                _LOGGER.warning("Unknown parameter requested: %s", pid)
                result[pid] = _inactive_param(f"Unknown param {pid}")

        return web.json_response(result)

    async def handle_ji(self, request: web.Request) -> web.Response:
        """Handle /JI — device info."""
        _LOGGER.info("JI request (device info) from %s", request.remote)
        return web.json_response(self.device_info)

    async def handle_js(self, request: web.Request) -> web.Response:
        """Handle /JS — set parameter."""
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"status": 2}, status=400)

        param_id = str(body.get("Parameter", ""))
        value = str(body.get("Value", ""))

        _LOGGER.info("JS request: set param %s = %s", param_id, value)

        if param_id in self.db:
            self.db[param_id]["value"] = value
            # Update desc for enum types
            if self.db[param_id]["dataType"] == 1:
                self.db[param_id]["desc"] = f"Set to {value}"
            return web.json_response({"status": 1})  # 1 = success

        _LOGGER.warning("JS: unknown parameter %s", param_id)
        return web.json_response({"status": 2})  # 2 = error

    async def handle_jv(self, request: web.Request) -> web.Response:
        """Handle /JV — JSON-API version."""
        _LOGGER.info("JV request (json-api version) from %s", request.remote)

        if self.json_api_unavailable:
            _LOGGER.info("JV request simulated as unavailable (404)")
            return web.Response(status=404)

        return web.json_response({"api_version": self.json_api_version})

    def create_app(self) -> web.Application:
        """Create the aiohttp application."""
        app = web.Application()
        prefix = self._prefix()

        app.router.add_post(f"{prefix}/JQ", self.handle_jq)
        app.router.add_post(f"{prefix}/JI", self.handle_ji)
        app.router.add_post(f"{prefix}/JS", self.handle_js)
        app.router.add_post(f"{prefix}/JV", self.handle_jv)

        _LOGGER.info(
            "Routes registered: %sJQ, %sJI, %sJS, %sJV",
            prefix,
            prefix,
            prefix,
            prefix,
        )
        return app


def main() -> None:
    """Run the fake BSB-LAN server."""
    parser = argparse.ArgumentParser(
        description="Fake BSB-LAN server for testing multi-circuit config flows"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port to listen on (default: 8080)"
    )
    parser.add_argument(
        "--circuits",
        type=int,
        default=2,
        choices=[1, 2, 3],
        help="Number of active heating circuits (default: 2)",
    )
    parser.add_argument(
        "--passkey", type=str, default=None, help="Passkey prefix (default: none)"
    )
    parser.add_argument(
        "--omit-static-values",
        action="store_true",
        help="Omit heating circuit min/max temperature parameters from responses",
    )
    parser.add_argument(
        "--omit-dhw",
        action="store_true",
        help="Omit all DHW (hot water) parameters, simulating a device without DHW",
    )
    parser.add_argument(
        "--firmware-version",
        type=str,
        default=None,
        help=(
            "Override the reported firmware version (e.g. 1.0.0 to trigger the "
            "outdated firmware repair issue)"
        ),
    )
    parser.add_argument(
        "--json-api-version",
        type=str,
        default="2.0",
        help="JSON-API version returned by /JV (default: 2.0)",
    )
    parser.add_argument(
        "--json-api-unavailable",
        action="store_true",
        help="Simulate /JV not being retrievable (returns HTTP 404)",
    )
    args = parser.parse_args()

    server = FakeBSBLAN(
        num_circuits=args.circuits,
        passkey=args.passkey,
        omit_static_values=args.omit_static_values,
        omit_dhw=args.omit_dhw,
        firmware_version=args.firmware_version,
        json_api_version=args.json_api_version,
        json_api_unavailable=args.json_api_unavailable,
    )
    app = server.create_app()

    print(f"\n{'=' * 60}")
    print("  Fake BSB-LAN Server")
    print(f"  Circuits: {args.circuits}  |  Port: {args.port}")
    print(f"  MAC: {DEVICE_INFO['MAC']}")
    if args.passkey:
        print(f"  Passkey: {args.passkey}")
    if args.omit_static_values:
        print("  Static values: omitted")
    if args.omit_dhw:
        print("  DHW (hot water): omitted")
    print(f"  Firmware: {server.device_info['version']}")
    if args.json_api_unavailable:
        print("  JSON-API (/JV): unavailable (simulated 404)")
    else:
        print(f"  JSON-API (/JV): {server.json_api_version}")
    print(f"{'=' * 60}")
    print("\n  Add integration in HA with:")
    print("    Host: 127.0.0.1")
    print(f"    Port: {args.port}")
    if args.passkey:
        print(f"    Passkey: {args.passkey}")
    print(f"\n  The config flow should detect {args.circuits} circuit(s)")
    if args.circuits > 1:
        print("  and show the heating circuit selection step.")
    print()

    web.run_app(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
