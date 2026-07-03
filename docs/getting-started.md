# Getting Started

## Installation

```bash
pip install python-bsblan
```

## Configuration

Create a `BSBLANConfig` object with your device connection details:

```python
from bsblan import BSBLAN, BSBLANConfig

config = BSBLANConfig(
    host="192.168.1.100",
    passkey=None,           # Set if your device uses passkey auth
    username=None,          # Set for username/password auth
    password=None,
)
```

!!! warning "Security"
    Never hard-code credentials in your source code. Use environment variables
    or a secrets manager instead.

    ```python
    import os

    config = BSBLANConfig(
        host=os.getenv("BSBLAN_HOST", "192.168.1.100"),
        username=os.getenv("BSBLAN_USERNAME"),
        password=os.getenv("BSBLAN_PASSWORD"),
    )
    ```

## Basic usage

```python
import asyncio
from bsblan import BSBLAN, BSBLANConfig

async def main() -> None:
    config = BSBLANConfig(host="192.168.1.100")
    async with BSBLAN(config) as client:
        # Read current heating state
        state = await client.state()
        print(f"HVAC Mode: {state.hvac_mode.desc}")
        print(f"Current Temp: {state.current_temperature.value}")

        # Read sensor data
        sensor = await client.sensor()
        print(f"Outside Temp: {sensor.outside_temperature.value}")

        # Set thermostat
        await client.thermostat(target_temperature="21.5")

        # Get device info
        device = await client.device()
        print(f"Device: {device.name} v{device.version}")

asyncio.run(main())
```

## Firmware compatibility

On the first request the client lazily runs `initialize()`, which detects the
device's capabilities and selects a matching configuration based on the BSB-LAN
JSON-API version reported by the `/JV` endpoint:

- **Full configuration** — JSON-API version 2.0 or newer. All features are
  available, including multiple heating circuits, hot water control, schedules,
  sensors, and cooling setpoints.
- **Basic configuration** — JSON-API version 1.x. A reduced, single-circuit
  configuration covering essential heating, hot water, and sensor parameters.

The JSON-API version is the documented, firmware-independent compatibility
signal. The adapter firmware version (from `/JI`) is still retrieved and exposed
via `device_info`, but it is not used to determine support. A device that does
not expose `/JV`, or reports a JSON-API version below 1.0, raises
`BSBLANVersionError`.

Basic (JSON-API 1.x) support is best-effort and may not cover every parameter
your heating system exposes.

## Temperature bounds

For heating comfort setpoint writes (`target_temperature`), the lower bound is
the protective (frost) setpoint (`714` for circuit 1, `1014` for circuit 2),
which allows setpoints down to the frost-protection temperature. The reduced
setpoint (`712`/`1012`) is exposed as `min_temp` for reference and is used as a
fallback lower bound only when the protective setpoint is unavailable (for
example, on PPS devices). The upper heating bound is the comfort maximum (`716`
for circuit 1 and `1016` for circuit 2) when the device exposes those
parameters.

## Cooling setpoint support

Some BSB/LPB controllers expose a cooling comfort setpoint for each heating
circuit. The client maps BSB-LAN parameter `902` for circuit 1 and `1202` for
circuit 2 to `target_temperature_high`; the duplicate decimal parameters
`902.1` and `902.2` are not used.

When available, cooling setpoint validation uses `905`/`1205` (comfort setpoint
minimum) as the lower bound and `903`/`1203` (room temperature reduced setpoint)
as the upper bound. Parameters `908` and `1208` are flow setpoints and are not
used for room setpoint validation.

Cooling support is optional. During section validation, unsupported parameters
are removed from the active API map, so integrations can detect support by
checking whether `state.target_temperature_high` is present.

```python
async with BSBLAN(config) as client:
    state = await client.state(include=["target_temperature_high"])

    if state.target_temperature_high is not None:
        print(f"Cooling setpoint: {state.target_temperature_high.value}")
        await client.thermostat(target_temperature_high="24.0")
```

BSB-LAN writes one parameter at a time. If an application exposes a heat/cool
temperature range, write `target_temperature` and `target_temperature_high` with
separate `thermostat()` calls.

## Cooling operating mode

The cooling circuit has its own operating mode, separate from the heating
`hvac_mode` (`700`/`1000`) and the read-only changeover status (`900`/`1200`).
The client maps BSB-LAN parameter `901` for circuit 1 and `1201` for circuit 2
to `cooling_operating_mode`. Valid values are `0` (Protection), `1`
(Automatic), `2` (Reduced), and `3` (Comfort).

Like the cooling setpoint, the parameter is optional and removed from the
active API map when the device does not expose it, so integrations can detect
support by checking whether `state.cooling_operating_mode` is present.

```python
async with BSBLAN(config) as client:
    state = await client.state(include=["cooling_operating_mode"])

    if state.cooling_operating_mode is not None:
        print(f"Cooling mode: {state.cooling_operating_mode.desc}")
        await client.thermostat(cooling_operating_mode=1)
```

Setting `cooling_operating_mode` is not supported on PPS devices.

## PPS bus support

PPS bus devices are detected from the device metadata returned by BSB-LAN. The
client provides minimal climate support for PPS devices through the same climate
methods used by BSB/LPB devices.

Supported PPS climate operations:

- `state()` for `hvac_mode`, `target_temperature`, and `current_temperature`
- `static_values()` for `min_temp` and `max_temp`
- `thermostat()` for target temperature and HVAC mode
- `get_available_circuits()`, which returns `[1]` when the single PPS
  climate circuit is available, otherwise `[]`; PPS devices only ever expose
  circuit `1`

PPS devices currently have these limitations:

- Only circuit `1` is supported.
- `time()` and `set_time()` are not supported for PPS devices.
- `thermostat(hvac_mode=2)` is not supported on PPS devices. Valid PPS modes
    are `0` (off), `1` (auto), and `3` (heat/manual).
- Hot water and schedule helpers are intended for BSB/LPB devices.

Check `supports_time_sync` before showing or calling time synchronization in
applications:

```python
async with BSBLAN(config) as client:
    device = client.device_info or await client.device()
    print(f"Bus type: {device.bus or 'unknown'}")

    if client.supports_time_sync:
        device_time = await client.time()
        print(device_time.time.value)
```

## Hot water control

```python
from bsblan import SetHotWaterParam

async with BSBLAN(config) as client:
    # Read hot water state
    hw_state = await client.hot_water_state()
    print(f"DHW Mode: {hw_state.operating_mode.desc}")

    # Read hot water configuration
    hw_config = await client.hot_water_config()

    # Set hot water temperature
    await client.set_hot_water(SetHotWaterParam(nominal_setpoint=55.0))
```

## Multi-circuit support

```python
async with BSBLAN(config) as client:
    # Get available heating circuits
    circuits = await client.get_available_circuits()
    print(f"Available circuits: {circuits}")

    # Read state for a specific circuit
    state = await client.state(circuit=2)
```
