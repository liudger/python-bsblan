# Unified schedules (Plan A)

## Intent and scope

Replace the competing raw/structured schedule APIs with one schedule API for the
Home Assistant BSB-LAN integration. Breaking library changes are permitted. HA
entity identifiers, action names, existing action payloads, active-setpoint
behavior, temporary overrides, and targeted refreshes must remain unchanged.

The user approved Plan A and requested an implementation plan and continuation.
The detailed decisions below implement that direction; they do not authorize
publishing a release, pushing branches, or modifying a shared HA branch.

Deliver the library change first, then a dependent HA migration. These are
separate plans because they have different test environments and release gates.
Do not release the breaking library update without a tested HA migration.

## Baselines inspected

- Library branch: `feat/structured-schedule-reads`, HEAD `e96c5a3`.
- Relevant uncommitted library work: README, getting-started guide, control
  example, and `tests/test_control_example.py`.
- HA local checkout: `910c1f15ec66cfb560bc798b4b76627dcbf749fa`.
- Merged HA changes reviewed from GitHub: #176294 (nonblocking startup), #181360
  (heating schedules), #187852 (targeted readback), #187892 (setpoint numbers),
  #187891 (active climate setpoint), #188197 (active DHW setpoint), #188735 and
  #188940 (library upgrades). The local checkout predates #187891; it must not be
  used as the final integration baseline without updating an isolated branch.
- #185691 (PPS support) was open when checked; account for its capabilities, but
  do not treat it as merged code or rewrite it as part of this project.

## Approaches

1. **Plan A, selected:** retain the flat client interface, unify schedule models,
   configure mappings once, and migrate HA's schedule consumers. This solves the
   concrete inconsistencies without changing unrelated climate APIs.
2. **Plan B, deferred:** expose heating/hot-water domain objects across the
   library. This would require a much broader integration migration and does not
   independently solve mapping or write-safety problems.
3. **Compatibility wrappers, rejected:** keeping raw and structured readers and
   parallel payload types would preserve the ambiguity the refactor addresses.

## Global constraints

- Python 3.12+; use uv and the existing dependencies only.
- Treat API v3 as the supported baseline; do not reintroduce v1-only behavior.
- Response/state models use pydantic.BaseModel.
- Set-parameter payload models use @dataclass.
- Parameter names use `snake_case`; preserve `dhw_*` and `legionella_function_*` names.
- Send one /JS request per populated day, sequentially.
- No automatic discovery, guessed IDs, firmware-only profile selection, or live
  device writes during development.
- Unknown schedule mappings disable schedules, not ordinary climate monitoring.
- Keep total coverage at 95%+ and patch coverage at 100%.
- Run uv run prek run --all-files before finishing implementation changes.
- Preserve unrelated dirty files and untracked plans/OpenSpec work.

## Public API and ownership

Use `src/bsblan/schedules.py` for public schedule types and the single interval
codec; keep request orchestration in `_schedules.py`. General entity models stay
in `models.py`; the schedule module may import `DataType`/`EntityInfo` from there,
not the reverse.

```python
BSBLANConfig(..., schedule_mappings=ScheduleMappings(...))

await client.hot_water_schedule() -> ScheduleSnapshot
await client.heating_schedule(*, circuit: int = 1) -> ScheduleSnapshot
await client.set_hot_water_schedule(update: ScheduleUpdate) -> None
await client.set_heating_schedule(
    update: ScheduleUpdate, *, circuit: int = 1
) -> None
```

Remove `get_hot_water_schedule`, `get_heating_schedule`, schedule `include`
arguments, old raw schedule response classes, `HeatingSchedule`, `DHWSchedule`,
`WeeklySchedule`, `DHWTimeSwitchPrograms`, and `SetHotWaterParam.dhw_time_programs`.
No alternate schedule route through `set_hot_water()` may remain. Keep generic
`read_parameters()` for raw/diagnostic access. Factory reset is not a weekday
schedule and is not included in this API.

### Mapping configuration

`ScheduleMapping` is a frozen pydantic model containing exactly seven weekday
string IDs. Retain the existing conservative canonical-ID syntax and uniqueness
validation. `ScheduleMappings` is frozen and has optional `hot_water`,
`heating_1`, and `heating_2` fields; no mappings are supplied by default.

Capture a validated immutable configuration for each client. Reads and writes
resolve the same mapping; neither accepts a per-call override or learns a
mapping from a previous response. Capture the host/port/passkey endpoint identity
and reject schedule operations after it changes; recheck between sequential
writes and preserve partial progress. Concurrent connection mutation during
in-flight I/O is unsupported. Reject bool/non-integer/unsupported circuits
and known PPS before schedule requests. Reject writes when cached metadata says
bus writes are disabled, regardless of bus type.

A mapping is a caller assertion, not device-verified identity. HA must persist it
per config entry/target and group. Reconfirm after target, firmware/table,
controller, destination, or bus changes. No installation-specific mapping was
verified during this session; development must use explicitly synthetic IDs.

### Values, snapshots, and updates

- `TimeSlot` and `DaySchedule` are frozen dataclasses. Times are minute precision,
  naive, and strictly increasing within a slot. Day slots are normalized to an
  immutable tuple, limited to three, and may not overlap. Preserve input order.
- `DaySchedule.from_bsblan_format(value: str)` is the only interval parser. It
  accepts active `HH:MM-HH:MM` intervals and disabled `##:##-##:##` placeholders.
  Empty/inactive/null wire entities are handled before parsing, never converted
  into an empty day. Unsupported endpoint/interval shapes remain unparsed.
- `ScheduleUpdate` is a frozen dataclass with optional weekday `DaySchedule`
  fields. `None` means unchanged. An empty `DaySchedule` expresses clear intent;
  it must not be confused with missing observation data.
- `ScheduleDay` is frozen and contains `weekday`, `parameter_id`, status
  (`readable`, `empty`, `unavailable`, or `unparsed`), raw value, frozen copied
  entity metadata, structured schedule if available, and failure context.
- `ScheduleSnapshot` is frozen. `days` is a canonical Monday-to-Sunday tuple of
  seven `ScheduleDay` instances; `day(weekday)` provides lookup. It includes
  kind/circuit and a UTC receipt timestamp. `complete` and `retry_required` are
  derived properties included in JSON serialization, never mutable flags.
- `complete` requires all days to be `readable` or `empty`. `retry_required` is
  true for missing/inactive days or device errors other than code 7. An unparsed
  format alone does not schedule endless retries; retain the raw observation.
- Frozen metadata is a private frozen `EntityInfo[str]` specialization containing
  only the existing scalar metadata fields, not another public payload type.

The codec conservatively declines 24:00, overnight/equal/overlapping intervals,
non-minute precision, and unsupported physical slot counts. These limitations
must not be described as proof that a controller's program is invalid.

### Read behavior and failures

A read sends one /JQ request with all seven configured IDs. Map by exact response
key, never position or name. Do not query/reset factory defaults. Return all
seven outcomes even if the response is empty or entirely device errors. Keep
successful days if another day has an unsupported interval format.

Authentication/connection failures and malformed JSON/envelopes remain typed
exceptions. Malformed entity metadata remains a contextual
`BSBLANMalformedResponseError`; valid schedule text outside the supported
representation becomes an `unparsed` day, not that exception. Preserve decode
causes and existing transport retry behavior. Update the OpenSpec error contract
explicitly to distinguish corrupt responses from unavailable observations and
unsupported representations; do not promise permanent/transient recovery from
an exception name alone.

### Write behavior and failures

Validate mapping, update type, all populated days, serializability, clear
support, and known bus restrictions before the first write. Do not write a
snapshot, accept arbitrary strings, reset standard values, or skip unavailable
days by silently treating them as empty.

The inspected firmware's /JS response is keyed by parameter ID with an integer
`status`; status 1 is acknowledgement. A generic `{"status": "ok"}` test fixture
is not acknowledgement. Check the exact requested key and reject missing,
malformed, bool/string, or non-1 statuses. Acknowledgement is not readback proof.

On the first failed/rejected/uncertain write, stop and raise
`BSBLANScheduleWriteError` with kind/circuit, acknowledged weekdays, the failed
weekday/ID, unattempted weekdays, and outcome (`rejected` or `unknown`). Preserve
the original transport exception as the cause. The failed day may have been
applied when the outcome is unknown. Cancellation propagates; no rollback or
atomic-week guarantee is made. HA refreshes after any attempted write, including
partial failures, and owns verification/publication.

**Clear safety gate:** the inspected firmware requires at least one numeric
interval and does not establish empty-string clearing. Until a real-device
fixture establishes a supported clear encoding, reject updates containing an
empty day locally with `BSBLANUnsupportedFeatureError`, before writing any other
day. Do not invent a numeric disabled-slot encoding. Document this deliberate
safety restriction in the HA migration and release notes.

## Home Assistant migration boundary

Keep active/configured setpoints, temporary overrides, presets, number entities,
fast/slow polling, target-specific refreshes, entity IDs, and action schemas.
HA supplies confirmed mappings or leaves schedules disabled, builds the shared
`ScheduleUpdate`, serializes the new snapshots, and checks `retry_required`
before clearing pending refresh state. A newer incomplete observation must not
be silently presented as old data newly confirmed by the controller.

Add schedule mapping options without requiring them for setup. Unknown mappings
produce one actionable diagnostic/log outcome, not failed climate setup or a
repeated missing-profile network probe. Do not ship built-in profiles without
installation-specific evidence. Profile-entry UX and device clear verification
are explicit release prerequisites, not guessed implementation details.

## Examples and documentation

Create a separate read-only `examples/read_schedules.py` that accepts validated
mapping JSON and never calls setters. Remove the branch's schedule CLI additions
and automatic schedule writes from `control.py`; do not advertise a destructive
example as a way to inspect schedules. Keep existing unrelated control examples
unless their schedule-only types are removed. Update README, getting-started,
API references, migration notes, and the error-classification spec together.

## Verification and release gates

Use synthetic HTTP fixtures with independently specified literal IDs/statuses;
no live device is queried or written. Pin both mapping consistency and error
paths. Cover immutability, unavailable versus empty, unparsed formats, invalid
later days preventing earlier writes, acknowledgement rejection, partial/unknown
outcomes, and read-only CLI execution.

Run full library tests with coverage and all hooks. Run HA integration tests in a
separate HA worktree against the new library and current upstream integration,
including the merged setpoint/targeted-refresh regressions. Real-device mapping
and clearing evidence remain absent unless the user supplies it. Do not claim
hardware validation or release readiness from synthetic coverage.
