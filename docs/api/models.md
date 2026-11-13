# Models

Data models for BSB-LAN API responses.

## Core types

### EntityInfo

::: bsblan.EntityInfo

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

### ApiVersion

::: bsblan.ApiVersion

### Info

::: bsblan.Info

### DeviceTime

::: bsblan.DeviceTime
