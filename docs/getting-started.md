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

## Structured schedules

`hot_water_schedule()` and `heating_schedule(circuit=1)` return the same immutable
`ScheduleSnapshot` type. Their setters accept a shared `ScheduleUpdate`. Reads
and writes use **one caller-confirmed mapping per target and group**, configured
once when creating the client. No default profile or per-call override is used.

Without a mapping, that group raises `BSBLANScheduleMappingError` before schedule
I/O; ordinary climate monitoring remains available. Known PPS schedules are
rejected locally with `BSBLANUnsupportedFeatureError`. Initialization can still
make its normal device and JSON-API version requests before a schedule call.

### Confirm and configure the mapping

Independently confirm the target/bus, exact active firmware/controller table,
and each weekday's parameter ID for the installation. A matching active
configuration/table together with a controller display or documentation can
provide this evidence; a source table alone does not prove it is active.
Successful responses, matching names/types, or equal firmware versions do not
establish day assignments. Unknown bus metadata is not evidence of BSB/LPB.
Leave schedules unconfigured if these facts cannot be confirmed.

Each ID is a unique canonical positive string, optionally followed by one
nonzero decimal digit (for example `502.1`). This conservative syntax is not a
firmware-wide support claim or an established maximum ID. Firmware may use
floating-point parsing or format response keys differently; confirm exact
request/response key agreement as well.

The following variables are placeholders for independently confirmed strings,
not universal parameter IDs:

```python
from bsblan import BSBLAN, BSBLANConfig, ScheduleMapping, ScheduleMappings

confirmed_mapping = ScheduleMapping(
    monday=confirmed_monday_id,
    tuesday=confirmed_tuesday_id,
    wednesday=confirmed_wednesday_id,
    thursday=confirmed_thursday_id,
    friday=confirmed_friday_id,
    saturday=confirmed_saturday_id,
    sunday=confirmed_sunday_id,
)
config = BSBLANConfig(
    host="YOUR_BSBLAN_IP",
    schedule_mappings=ScheduleMappings(heating_1=confirmed_mapping),
)

async with BSBLAN(config) as client:
    snapshot = await client.heating_schedule(circuit=1)
    monday = snapshot.day("monday")
    if monday.schedule is not None:
        for slot in monday.schedule.slots:
            print(slot.start, slot.end)
    print(snapshot.model_dump(mode="json"))
```

Use separate `hot_water`, `heating_1`, and `heating_2` mappings. Persist their
`model_dump()` output with the target identity in the consumer's configuration;
the library does not discover, persist, or select profiles. Reconfirm after
changes to target, firmware/table, controller, bus, or destination. Create a new
client to change mappings; existing clients retain their captured configuration.
Changing host, port, or passkey after construction invalidates schedule operations
with reason `target_changed`. A change between day writes stops the update and
preserves partial progress. Do not mutate connection options during in-flight
requests; this is not a concurrent reconfiguration API.

### Interpret observations

Every read requests all seven days and maps by exact ID. `snapshot.days` is a
Monday-to-Sunday tuple; use `snapshot.day("monday")` for lookup. Each day retains
its parameter ID, raw value, immutable metadata, status, and error/reason context.

- `readable`: parsed active intervals.
- `empty`: all reported physical slots are disabled (`##:##-##:##`).
- `unavailable`: missing ID, null/inactive value, or device error; no writable day.
- `unparsed`: text outside the supported representation; raw text is retained,
  other days survive, and there is no writable day.

`complete` is derived from all days being readable/empty. `retry_required` advises
another read for missing/inactive values and device errors other than code 7;
unparsed text alone does not require endless retries. These are facts/advice,
not promises of permanent support or eventual recovery. No negative capability
is cached. Malformed JSON/envelopes/metadata still raise contextual
`BSBLANMalformedResponseError`; auth/connection failures stay typed exceptions.

The codec accepts up to three minute-precision, non-overlapping intervals. It
conservatively declines 24:00, overnight/equal intervals and other unsupported
formats; this does not prove the controller's program invalid. The UTC receipt
timestamp is not controller time, an atomic-week guarantee, or write verification.
Raw formatting and disabled-slot positions are not reproduced by serialization.

### Write an explicit partial update

```python
from bsblan import DaySchedule, ScheduleUpdate

update = ScheduleUpdate(
    tuesday=DaySchedule.from_bsblan_format("06:00-08:00 17:00-21:00"),
)
# This changes the device: invoke explicitly on a correctly configured client.
await client.set_heating_schedule(update, circuit=1)
```

`None` leaves a day unchanged. The entire update is validated before any write;
then each populated day gets one sequential `/JS` request using the same mapping
as reads. Only integer status 1 under that parameter's key counts as
acknowledgement—not readback. On rejection or uncertainty,
`BSBLANScheduleWriteError` reports acknowledged days, the failed day/ID,
unattempted days, and the original transport cause when present. There is no
rollback. An uncertain failed day may have changed; the consumer owns refresh
and state publication, including after partial failures.

**Clearing is not yet verified:** an empty `DaySchedule()` expresses clear intent
but is rejected locally before _any_ update writes. The library does not assume
an empty string clears the controller. Known read-only bus metadata also blocks
writes. Do not turn unavailable/unparsed observations into clear commands.

### Read-only command-line example

After setting `BSBLAN_HOST` and any required credentials:

```bash
uv run python examples/read_schedules.py \
  --hot-water-mapping "$CONFIRMED_HOT_WATER_MAPPING" \
  --heating-mapping "$CONFIRMED_HEATING_MAPPING" --circuit 1
```

Each JSON object has the seven lowercase weekday names and confirmed string
IDs. Omit a mapping to skip that group. This separate example prints JSON
observations and has no write mode. `examples/control.py` still changes device
settings and is not a schedule inspection tool.

See the [breaking API migration guide](schedule-migration.md) before updating an
integration. Generic `read_parameters()` remains available for raw diagnostics
without asserting weekday roles.

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
