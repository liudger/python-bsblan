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
