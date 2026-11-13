# Client

The main entry point for interacting with BSB-LAN devices.

## BSBLAN

::: bsblan.BSBLAN
options:
show_bases: false
members: - **init** - initialize - device_info - supports_time_sync - get_available_circuits - state - sensor - static_values - device - info - time - set_time - thermostat - heating_schedule - set_heating_schedule - hot_water_state - hot_water_config - hot_water_schedule - set_hot_water - set_hot_water_schedule

## BSBLANConfig

::: bsblan.BSBLANConfig
options:
show_bases: false

## Shared schedule API

Read and write methods share the immutable mappings in
`BSBLANConfig.schedule_mappings`. Missing groups have no implicit profile.
See [structured schedules](../getting-started.md#structured-schedules) and the
[breaking API migration guide](../schedule-migration.md).

The [shared models](models.md#schedules) describe mappings, snapshots, intervals,
and partial updates. [Schedule exceptions](exceptions.md) expose absent mappings
and acknowledged/uncertain partial-write progress.
