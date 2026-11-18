# Models

Data models for BSB-LAN API responses.

## Core types

### EntityInfo

::: bsblan.EntityInfo

`read_write_permission` distinguishes explicit readable/writable (`True`), denied
or write-only (`False`), and absent permission metadata (`None`). Firmware
`readwrite` codes are 0=read/write, 1=read-only, 2=write-only—not booleans. Missing
fields retain their legacy numeric defaults without granting affirmative proof.
Both permission fields require integer JSON values.

### EntityValue

::: bsblan.EntityValue

## Heating

### State

::: bsblan.State

### StaticState

::: bsblan.StaticState

### Sensor

::: bsblan.Sensor

## Hot water

### HotWaterState

::: bsblan.HotWaterState

### HotWaterConfig

::: bsblan.HotWaterConfig

### SetHotWaterParam

::: bsblan.SetHotWaterParam

## Schedules

Heating and DHW share immutable observations and a separate partial-update
payload. See the [migration guide](../schedule-migration.md) for breaking changes.

### ScheduleMapping

::: bsblan.ScheduleMapping

### ScheduleMappings

::: bsblan.ScheduleMappings

### ScheduleProfileIdentity

::: bsblan.ScheduleProfileIdentity

### ScheduleProfile

::: bsblan.ScheduleProfile

### ScheduleAvailability

::: bsblan.ScheduleAvailability

### ScheduleCandidateProbe

::: bsblan.ScheduleCandidateProbe

A diagnostic candidate is never enabled, even when compatible. Its proposed
mapping requires independent active-table/weekday confirmation before use.

See [profile evidence and compatibility](../schedule-profiles.md) before adding
profiles. The standard registry includes one narrowly scoped, verified RVS21
entry. `ScheduleProfile.table_parameters` declares immutable ID/name pairs covering
every mapped ID exactly once; a matching profile can then recognize each group's
active `/JC` layout without a caller `schedule_table` assertion.

### ScheduleSnapshot

::: bsblan.ScheduleSnapshot

### ScheduleDay

::: bsblan.ScheduleDay

### ScheduleUpdate

::: bsblan.ScheduleUpdate

### DaySchedule

::: bsblan.DaySchedule

### TimeSlot

::: bsblan.TimeSlot

## Device

### Device

::: bsblan.Device

`busdest` is optional but strictly integer when present: no coercion of booleans,
floats or numeric strings into a profile identity. Missing/null stays unknown.

`is_bus_writable` reflects the gateway default indicator. On BSB/LPB it is not an
absolute veto on individual active-table parameters; see
[parameter permissions](../schedule-profiles.md#parameter-permissions-versus-gateway-defaults).

### ApiVersion

::: bsblan.ApiVersion

### Info

::: bsblan.Info

### DeviceTime

::: bsblan.DeviceTime
