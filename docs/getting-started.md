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

## Reduced setpoint and temporary override

The reduced room setpoint (`712` for circuit 1, `1012` for circuit 2) can be
written with `temp_reduced_setpoint`. It uses the same bounds as
`target_temperature`.

To switch a circuit to comfort or reduced only until the next time program
switch point, write `temporary_mode` (`10110` for circuit 1, `10111` for circuit
2): `0` (no override), `1` (reduced), or `2` (comfort). The override only has an
effect in automatic mode and cannot be read back.

```python
async with BSBLAN(config) as client:
    await client.thermostat(temp_reduced_setpoint="18.0")
    await client.thermostat(temporary_mode=2)
```

Setting `temp_reduced_setpoint` and `temporary_mode` is not supported on PPS
devices.

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
    state = await client.state(include=["hvac_mode", "cooling_operating_mode"])

    if state.cooling_operating_mode is not None:
        print(f"Cooling mode: {state.cooling_operating_mode.desc}")
        await client.thermostat(cooling_operating_mode=1)
```

Setting `cooling_operating_mode` is not supported on PPS devices.

## Active setpoints

In automatic mode the controller switches between the comfort setpoint
(`710`/`1010`) and the reduced setpoint (`712`/`1012`) following the time
program, and room units can shift it temporarily. `target_temperature` always
holds the comfort setpoint. The setpoint the controller currently applies is
exposed as `current_setpoint` (`8741` for circuit 1, `8771` for circuit 2).

Hot water works the same way: `nominal_setpoint` (`1610`) applies during the
release periods (`1620`) and `reduced_setpoint` (`1612`) outside them. The
setpoint currently applied is exposed as `dhw_current_setpoint` (`8831`).

```python
async with BSBLAN(config) as client:
    state = await client.state(include=["target_temperature", "current_setpoint"])
    hw_state = await client.hot_water_state(include=["dhw_current_setpoint"])
```

## PPS bus support

PPS bus devices are detected from the device metadata returned by BSB-LAN. The
client provides minimal climate support for PPS devices through the same climate
methods used by BSB/LPB devices.

Supported PPS climate operations:

- `state()` for `hvac_mode`, `target_temperature`, and `current_temperature`
- `static_values()` for `min_temp` and `max_temp`
- `sensor()` for `outside_temperature` (`15030`) and `current_temperature` (`15008`)
- `thermostat()` for target temperature and HVAC mode
- `get_available_circuits()`, which returns `[1]` when the single PPS
  climate circuit is available, otherwise `[]`; PPS devices only ever expose
  circuit `1`

PPS sensor parameters are selected only when device metadata identifies the PPS
bus. BSB/LPB devices retain their existing sensor mappings. Sensor reads remain
on demand; `sensor(include=["outside_temperature"])` requests only `15030` on PPS
and only `8700` otherwise, without probing both parameter ranges.

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

## Structured schedule reads

`get_hot_water_schedule(mapping=...)` and `get_heating_schedule(circuit=1,
mapping=...)` require a separate caller-confirmed seven-day `ScheduleReadMapping`
for the current target and group. On the BSB/LPB route, without one they raise
`BSBLANScheduleMappingError` before that get call sends its schedule request.
Known PPS is rejected first with `BSBLANUnsupportedFeatureError`.
Existing client initialization (including `async with BSBLAN(config)`) can make
its own device and version requests first. The mapping is a caller
assertion for BSB/LPB, not verified or discovered by the library; even seven
successful TIMEPROG responses do not verify weekdays. Reconfirm after changes to
firmware, active table, controller, bus or destination. Unknown bus metadata is
not proof of BSB/LPB; confirm it independently. Known PPS is rejected locally by
these new methods; PPS support is not established and existing PPS routes are
unchanged. No automatic discovery or default profile is used.

Each ID must be a unique canonical positive string, optionally followed by one
nonzero decimal digit (for example `502.1`). This is a conservative syntax
limit, not a claim about every firmware. Populate the seven fields only from a
mapping independently confirmed for your target; no example IDs below are safe
to assume for a particular device.

Confirm the active target and bus, the exact active firmware/controller table,
and the parameter ID for each weekday and group against independently reliable
information for that installation, such as a matching active configuration or
table together with a controller display or documentation identifying each day.
Source code or a table alone does not establish that it is active on the target;
matching value types, names, firmware versions or successful responses do not
prove the day assignments. If any fact cannot be confirmed, leave the mapping
unknown and do not call the structured reader. Reconfirm after relevant changes.
The consumer must configure and persist mappings separately by target and group
(for example heating circuit 1, heating circuit 2, and hot water); the library
does not store or select them. The following variables are placeholders for
seven independently confirmed strings, not universal IDs or device data:

```python
from bsblan import ScheduleReadMapping

confirmed_mapping = ScheduleReadMapping(
    monday=confirmed_monday_id,
    tuesday=confirmed_tuesday_id,
    wednesday=confirmed_wednesday_id,
    thursday=confirmed_thursday_id,
    friday=confirmed_friday_id,
    saturday=confirmed_saturday_id,
    sunday=confirmed_sunday_id,
)
# A consumer can persist confirmed_mapping.model_dump() with the target and
# group in its own configuration and reconstruct it with model_validate().
```

The accepted syntax does not establish an exactness limit for arbitrarily large
IDs: firmware may use floating-point numbers and format response keys differently.
Use only independently confirmed IDs with exact request/response key agreement;
no maximum device ID is established here.

```python
from copy import deepcopy

async with BSBLAN(config) as client:
    # confirmed_mapping is a ScheduleReadMapping for this target and group.
    snapshot = await client.get_hot_water_schedule(mapping=confirmed_mapping)
    monday = snapshot.days["monday"]
    if monday.status == "readable" and monday.schedule is not None:
        edit_copy = deepcopy(monday.schedule)
        for slot in edit_copy.slots:
            print(slot.start, slot.end)
```

Each day exposes its parameter ID, status, original `raw_value`, entity metadata,
reason, `reason_code`, `error_code`, advisory `retry_hint`, and `schedule`.
`mapping_source='explicit'` and `day_assignment='caller_configured'` describe
the source of day labels; `source='device_response'` describes values only.
`empty` means a response made entirely
of disabled slots; missing IDs, null and inactive sentinels are `unavailable`,
not an empty schedule. `complete` is false if any day is unavailable. Malformed
values or unsupported formats raise `BSBLANMalformedResponseError`. Completely
missing or device-error responses remain incomplete snapshots with all seven
day outcomes. Code 7 suggests reconfiguration; 261 suggests retrying later;
other errors and missing/inactive values have unknown retryability. These are
advice, not promises, and no negative capability is cached.

The UTC `received_at` timestamp is when the library records the processed
response, not exact byte receipt or controller time. A snapshot is not an atomic
week or confirmation of a write. The original
raw text is retained; slot parsing preserves interval boundaries, not disabled
slot positions or exact formatting. No snapshot is automatically converted to a
write payload. Snapshots and nested objects are mutable: status, raw value and
completeness describe the original observation and are not recomputed after
mutation. Copy before editing and use `snapshot.model_dump(mode="json")` for JSON.
The existing writers do not receive the read mapping and may write a different
ID, especially for decimal profiles. A read does not demonstrate a safe writer
roundtrip. Writes are separate, potentially partial operations and their device
acceptance, including an empty-string clear, is not confirmed by this API.
The structured representation conservatively rejects 24:00, overnight, equal,
or overlapping intervals; that does not prove a controller program invalid.
The existing raw `hot_water_schedule()` and `heating_schedule()` methods remain
available.

## Multi-circuit support

```python
async with BSBLAN(config) as client:
    # Get available heating circuits
    circuits = await client.get_available_circuits()
    print(f"Available circuits: {circuits}")

    # Read state for a specific circuit
    state = await client.state(circuit=2)
```

`get_available_circuits()` reads parameter `6217` (check number heating circuits), where each heating circuit has a two-digit column starting from the right, and returns the circuits whose column is not `00`. When the controller does not give a usable value for `6217`, it keeps each circuit whose operating mode (`700` or `1000`) has a value.
