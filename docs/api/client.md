# Client

The main entry point for interacting with BSB-LAN devices.

## BSBLAN

<!-- prettier-ignore-start -->

::: bsblan.BSBLAN
    options:
      show_bases: false
      members:
        - __init__
        - initialize
        - device_info
        - supports_time_sync
        - get_available_circuits
        - state
        - sensor
        - static_values
        - device
        - info
        - time
        - set_time
        - thermostat
        - discover_schedules
        - invalidate_schedule_profiles
        - probe_schedule_candidate
        - heating_schedule
        - set_heating_schedule
        - hot_water_state
        - hot_water_config
        - hot_water_schedule
        - set_hot_water
        - set_hot_water_schedule

## BSBLANConfig

::: bsblan.BSBLANConfig
    options:
      show_bases: false

<!-- prettier-ignore-end -->

## Shared schedule API

Read and write methods share the immutable manual overrides in
`BSBLANConfig.schedule_mappings`. Heating mappings are configured under
`heating={1: profile_1, 2: profile_2}` and selected by the same `circuit` identifier
used by the read/write methods. Missing groups attempt evidence-backed automatic
resolution using `schedule_profiles`, matching declared `table_parameters` or an
asserted active `schedule_table`. The built-in RVS21 profile covers only the
verified controller/build/bus/destination and integer-weekday layout. Unknown
installations never receive guessed fallback IDs; `schedule_profiles=()` opts out.

`discover_schedules(refresh=False)` performs no writes and returns HC1, HC2 and
DHW `ScheduleAvailability` outcomes independently. Manual overrides take precedence.
Successful automatic mappings are reused in memory, never their schedule values.
Use `refresh=True` for fresh discovery or synchronous
`invalidate_schedule_profiles()` to discard trust without I/O. HA controls when
to discover, so it can defer work until initial polling settles. Initialization
never starts discovery, and the library does not impose a startup sleep.

Automatic groups require exact identity and seven compatible TIMEPROG parameters;
unknown/incompatible groups need a repair/override, while incomplete probes need
retries. Network/authentication/malformed exceptions propagate unchanged.
Readers/setters use the same resolution lazily and raise
`BSBLANScheduleProbeError` for inconclusive probes, not a mapping error. Reads
fetch fresh values using cached mappings; automatic writes always refresh identity
and compatibility first. Connection failures and observed metadata changes discard
automatic trust; explicit refresh/invalidation handles known remote changes.

`probe_schedule_candidate("issue_1668_dhw")` performs an explicit read-only probe
of the issue's seven decimal DHW IDs. Its immutable `ScheduleCandidateProbe`
result is **never enabled** and always requires confirmation of weekday meaning.
It does not populate the automatic mapping cache or run as a fallback on failure.
See [evidence-backed profiles](../schedule-profiles.md) for identity provenance,
current limitations and consumer retry/repair guidance.
See [structured schedules](../getting-started.md#structured-schedules) and the
[breaking API migration guide](../schedule-migration.md).

BSB/LPB gateway `buswritable=0` is a default indicator, not an absolute write veto.
Schedule setters can proceed with explicit individual `readwrite=0` evidence,
checking fresh `/JC` structures for the populated IDs when needed. Explicit
read-only/write-only flags remain denied; see
[parameter permissions](../schedule-profiles.md#parameter-permissions-versus-gateway-defaults).

The [shared models](models.md#schedules) describe mappings, snapshots, intervals,
and partial updates. [Schedule exceptions](exceptions.md) expose absent mappings
and acknowledged/uncertain partial-write progress.
