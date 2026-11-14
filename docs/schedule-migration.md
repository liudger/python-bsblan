# Breaking schedule API migration

This branch replaces the parallel raw/structured schedule APIs. **It requires a
coordinated Home Assistant update; it is not a drop-in replacement for the
currently released integration.** No release version or device-wide default
profile is implied by these instructions.

## API replacements

| Previous API                                                            | Replacement                                                                                       |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `get_heating_schedule(mapping=..., circuit=...)`                        | Configure `BSBLANConfig.schedule_mappings.heating[circuit]`, then `heating_schedule(circuit=...)` |
| `get_hot_water_schedule(mapping=...)`                                   | Configure `BSBLANConfig.schedule_mappings.hot_water`, then `hot_water_schedule()`                 |
| Raw `heating_schedule(include=...)` / `hot_water_schedule(include=...)` | Both return seven-day `ScheduleSnapshot` observations; no include argument                        |
| `ScheduleReadMapping`                                                   | `ScheduleMapping`, shared by reads and writes                                                     |
| Per-call read mappings / fixed writer IDs                               | `ScheduleMappings` captured once per client                                                       |
| `HotWaterSchedule` / `HeatingTimeSwitchPrograms`                        | `ScheduleSnapshot`                                                                                |
| `HeatingSchedule` / `DHWSchedule` / `WeeklySchedule`                    | `ScheduleUpdate`                                                                                  |
| `DHWTimeSwitchPrograms` / `SetHotWaterParam.dhw_time_programs`          | Removed; use the configured schedule setter with `ScheduleUpdate`                                 |
| `snapshot.days["monday"]`                                               | `snapshot.day("monday")`; `days` is a canonical immutable tuple                                   |
| Mutable day slot lists / edit-in-place copies                           | Frozen `TimeSlot` / `DaySchedule`; construct replacement values                                   |
| Per-day `retry_hint` and mutable `complete` flag                        | Derived `snapshot.retry_required` and `snapshot.complete`, plus day status/error context          |
| Schedule-only classes imported from `bsblan.models`                     | Import shared types from `bsblan` or `bsblan.schedules`                                           |
| `TimeSlot.from_bsblan_format()` / `to_bsblan_format()`                  | Parse/serialize the complete `DaySchedule` using the single codec                                 |
| Raw/factory-reset schedule fields and implicit group tables             | Generic `read_parameters()` for diagnostics; factory reset is not a weekday update                |

The `source`, `mapping_source`, and `day_assignment` snapshot fields are removed:
values are device-response observations and weekday assignment is always a
caller-configured assertion. There is no discovery or verified-profile variant.

## Configure once, use the same mapping for reads and writes

Build a `ScheduleMapping` from seven **independently confirmed** string IDs for
that installation, target, and group, then pass it to the client:

```python
from bsblan import BSBLANConfig, ScheduleMappings

config = BSBLANConfig(
    host="YOUR_BSBLAN_IP",
    schedule_mappings=ScheduleMappings(
        heating={1: confirmed_heating_mapping},
        hot_water=confirmed_hot_water_mapping,
    ),
)
```

Heating profiles are stored in a collection keyed by circuit number, e.g.
`heating={1: confirmed_mapping_1, 2: confirmed_mapping_2}`. Operations use the same
identifier: `heating_schedule(circuit=2)` selects the profile under key `2`.
The earlier draft's individually numbered fields are removed, not retained as
aliases. Canonical JSON keys `"1"`/`"2"` normalize to integers; ambiguous or
unsupported keys are rejected. The collection remains immutable and supports
JSON serialization and ordinary configuration deep copies.

Unconfigured groups raise `BSBLANScheduleMappingError` before schedule I/O. They
do not fall back to the old integer IDs, trigger availability discovery, or
prevent non-schedule climate monitoring. Invalid mapping construction fails
validation locally. Known PPS schedules remain unsupported.

Do not infer a mapping from firmware version, descriptions, sequential IDs, or
seven successful TIMEPROG responses. Persist it per HA config entry/group and
reconfirm after changing target, controller, active table, bus, firmware, or
destination. The library captures mappings at client construction; recreate the
client to change them. Retargeting an existing client/config is not a supported
way to transfer a confirmed mapping to another device. Host, port, or passkey
changes are rejected at schedule request boundaries with reason `target_changed`.
If this happens between day writes, the partial-write error retains progress and
chains the mapping error as its cause. Do not mutate connection configuration
while I/O is in flight; this is not a concurrent reconfiguration API.

## Observation and command semantics

`ScheduleSnapshot`, its seven days, their metadata, and parsed interval values
are immutable. `received_at` is an aware UTC processing/receipt timestamp, not
controller time or an atomic-week guarantee. JSON diagnostics use
`snapshot.model_dump(mode="json")`.

Each day is `readable`, `empty`, `unavailable`, or `unparsed`:

- Only readable/empty days have a parsed `DaySchedule`.
- Missing IDs, inactive values, and device errors are unavailable, never empty.
- Unsupported text is retained as unparsed; other days remain usable.
- Unsupported 24:00/overnight/equal/overlapping intervals do not prove the device
  has an invalid program. Generic parameter reads retain raw diagnostic access.

`ScheduleUpdate` is a frozen dataclass with optional weekday fields. `None`
means unchanged; updates never silently replace the whole week. To edit an
observation, construct replacement values, for example with `dataclasses.replace`:

```python
from dataclasses import replace
from datetime import time

from bsblan import ScheduleUpdate

monday = snapshot.day("monday")
if monday.status == "readable" and monday.schedule is not None:
    first = replace(monday.schedule.slots[0], start=time(5, 30))
    replacement = replace(
        monday.schedule,
        slots=(first, *monday.schedule.slots[1:]),
    )
    update = ScheduleUpdate(monday=replacement)
    # Submit explicitly; observe the write/readback rules below.
```

New intervals must be naive, minute-precision times, with increasing endpoints,
no overlaps, and no more than three intervals per day. The complete update is
validated before the first write, including validation of copied nested values.

**Clear restriction:** `DaySchedule()` expresses explicit clear intent, but its
wire encoding has not been verified. Any update containing an empty day raises
`BSBLANUnsupportedFeatureError` before any days are written. Do not send an empty
string or invent a numeric disabled-slot encoding. This restriction also applies
to the existing HA action's empty-day intent; report it as unsupported rather
than claim success. Installation-specific device evidence is needed to enable
clearing later.

## Acknowledgement, partial writes, and readback

Writers send one sequential `/JS` request per populated day. Only integer
`status: 1` under the exact requested ID acknowledges that day. Generic success
objects, bool/string statuses, and HTTP 200 alone do not acknowledge a change.

`BSBLANScheduleWriteError` reports:

- `kind`, `circuit`, `failed_day`, and `parameter_id`;
- `acknowledged_days`: requests explicitly acknowledged before the failure;
- `unattempted_days`: days never sent after the failed request;
- `outcome`: `rejected` for an explicit integer rejection, otherwise `unknown`;
- `__cause__`: the original transport/decode exception when one occurred.

Unknown means the failed day **may have changed**, including when a response was
lost. Acknowledgement is not readback proof. There is no atomic-week transaction,
automatic rollback, optimistic publication, or implicit readback. Cancellation
propagates rather than becoming a rejected write.

## Home Assistant migration checklist

Use current upstream HA, including the merged active-setpoint, number-entity,
heating-schedule, targeted-refresh, and nonblocking-startup changes. The older
local checkout used for the initial review is not the final integration baseline.

1. Add optional, validated per-entry schedule mapping configuration. No mapping
   must disable schedules only, not climate setup. Invalidate mappings on target
   reconfiguration; do not silently transfer them to a new host.
2. Replace `HotWaterSchedule`/`HeatingTimeSwitchPrograms` coordinator fields with
   the shared snapshot type. Serialize with `mode="json"` for diagnostics.
3. Do not clear pending schedule-refresh state merely because a snapshot exists.
   Inspect `retry_required`; incomplete missing/inactive/transient observations
   still need a later read. Preserve refresh-generation guards across writes.
4. Expose incomplete observations honestly. Do not label carried-over values as
   newly confirmed by the controller when a newer response omits those days.
5. Construct `ScheduleUpdate` in both action handlers. Preserve action names,
   target validation, weekday schemas, entity IDs, and omitted-day semantics.
6. Keep readback in HA, including after partially failed or uncertain writes.
   Preserve the original service error if the follow-up refresh also fails.
7. Keep climate/DHW active versus configured setpoints, temporary overrides,
   presets, number entities, fast/slow polling, and targeted state refreshes
   unchanged. Acknowledgement alone must not publish guessed entity state.
8. Test the integration against the new library before pinning a real release.
   Do not commit an unpublished version or local path as its dependency.

The dependent implementation plan is
[Home Assistant migration](superpowers/plans/2026-11-13-ha-unified-schedules.md).
The still-open PPS PR requires separate rebase/review against current HA; do not
restore removed preset/write helpers just to apply an old patch.

## Validation limits

The library tests use synthetic HTTP fixtures with explicit literal mappings.
They do not validate the active weekday table of a real installation, confirm
controller readback after a write, or establish a safe clear encoding. No live
device writes or profile discovery were performed. The breaking library change
must not be released as integration-compatible until the HA migration is tested.
