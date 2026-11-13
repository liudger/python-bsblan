# Unified Schedules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace parallel schedule APIs with one mapping-consistent, structured,
read/write API and provide the contract needed by a coordinated HA migration.

**Architecture:** Keep `BSBLAN` as a flat facade. Put schedule value/response types
and the interval codec in public `bsblan.schedules`, and keep device I/O in
`_schedules.py`. Bind immutable mappings once per client and remove all competing
schedule paths before release.

**Tech Stack:** Python 3.12+, dataclasses, existing pydantic/aiohttp, uv, pytest,
aresponses, Ruff, ty, prek; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-13-unified-schedules-design.md`

## Global Constraints

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
- Keep HA entity/action identities and merged setpoint/targeted-refresh behavior.
- Never push, publish, or modify the shared HA dev branch during this plan.

## Review Focus

- A missing or unparsed day must never become a clear command; test in Tasks 1/3.
- A valid first day plus an invalid later day must send zero writes; Task 3.
- A lost response after a write is uncertain, not evidence nothing changed;
  preserve partial progress and the transport cause in Task 3.
- Frozen snapshots must not hide mutable nested slots, days, metadata, or input
  aliases; test attempts to mutate every level in Task 1.
- Known PPS/read-only devices and absent mappings must be rejected before
  schedule I/O, without breaking unrelated climate reads; Task 2/3.

## Workspace and execution

- [ ] Obtain consent for an isolated worktree; the current checkout contains
      unrelated user edits. Preferred sibling path after consent:
      `/Users/liudger/Git/python-bsblan-unified-schedules`, branch
      `refactor/unified-schedules`, starting at `e96c5a3`.
- [ ] Carry only related WIP into that worktree: README, getting-started,
      `examples/control.py`, `tests/test_control_example.py`, and these design/plans.
      Keep OpenSpec skill metadata, thermostat proposal, and `plans/` untouched.
- [ ] Run `uv sync --dev` and `npm ci` using the repository lockfiles; then run
      `uv run pytest -n 4`. Record the actual baseline count and coverage.
- [ ] Use native inline execution (no subagent tool is installed), with this
      plan's isolated ledger and a separate final self-review. Do not pause between
      implementation tasks once the workspace and plan have been approved.
- [ ] Use explicit-path local commits per task; do not stage unrelated WIP.

## File structure

| Path                                          | Responsibility                                                   |
| --------------------------------------------- | ---------------------------------------------------------------- |
| `src/bsblan/schedules.py` (new)               | Shared public types, immutable observations, interval codec      |
| `src/bsblan/_schedules.py`                    | Mapping resolution, seven-day reads, validated sequential writes |
| `src/bsblan/bsblan.py`                        | Config field, collaborator wiring, four schedule methods         |
| `src/bsblan/models.py`                        | Remove superseded schedule definitions and raw write fields      |
| `src/bsblan/_hot_water.py`                    | State/configuration only, no schedule bypass                     |
| `src/bsblan/constants.py`                     | Remove obsolete fixed schedule API group mappings only           |
| `src/bsblan/exceptions.py`                    | Contextual mapping and partial-write errors                      |
| `src/bsblan/__init__.py`                      | The single supported public export surface                       |
| `tests/test_unified_schedule_models.py` (new) | Immutable values, codec, derived outcomes                        |
| `tests/test_unified_schedules.py` (new)       | Real HTTP read/write and routing regressions                     |
| Existing schedule/transport tests             | Migrate retained behavior, delete only obsolete API assertions   |
| `examples/read_schedules.py` (new)            | Standalone read-only inspection                                  |
| `tests/test_read_schedules_example.py` (new)  | CLI/config/read-only regression tests                            |
| Docs and error-classification spec            | API migration, error semantics, release restrictions             |

---

### Task 1: Shared immutable schedule values and observations

**Files:** Create `src/bsblan/schedules.py` and
`tests/test_unified_schedule_models.py`. Keep old definitions temporarily so the
existing API still runs until the facade migration.

**Interfaces:**

- Produces `Weekday` (lowercase Monday-Sunday Literal) and canonical `WEEKDAYS`.
- Produces frozen dataclasses `TimeSlot(start: time, end: time)`,
  `DaySchedule(slots: tuple[TimeSlot, ...] = ())`, and `ScheduleUpdate` with seven
  optional weekday `DaySchedule` fields defaulting to `None`.
- Produces `DaySchedule.from_bsblan_format(value: str) -> DaySchedule` and
  `DaySchedule.to_bsblan_format() -> str` (raises for an empty/unsupported write).
- Produces frozen pydantic `ScheduleMapping` (seven canonical unique IDs),
  `ScheduleMappings(hot_water=None, heating_1=None, heating_2=None)`,
  `ScheduleDay`, and `ScheduleSnapshot` as specified.
- Produces `ScheduleSnapshot.day(weekday: Weekday) -> ScheduleDay`, computed
  `complete: bool`, and computed `retry_required: bool`.

- [ ] **Step 1: Add failing value/codec tests.** Assert disabled placeholders are
      ignored, all-disabled text yields an empty tuple, active intervals retain
      order, and three intervals roundtrip. Cover >3 physical slots, malformed
      text, inactive/empty/null inputs, 24:00, overnight/equal/overlapping intervals,
      timezone-aware or second/microsecond-precision times, and invalid day types.
      Inputs must be checked before being serialized into a write command.
- [ ] **Step 2: Run** `uv run pytest --no-cov -n 0 tests/test_unified_schedule_models.py`.
      Expected: RED because the new API/behavior does not exist.
- [ ] **Step 3: Implement the value types and codec.** Accept list construction
      ergonomically but defensively normalize slots into tuples. Use one canonical
      parser, never the existing permissive parser plus another private parser.
- [ ] **Step 4: Add failing mapping/snapshot tests.** Use literal IDs
      `700,700.1,700.2,700.3,700.4,700.5,700.6` as synthetic inputs. Reject duplicate,
      missing, extra, numeric/bool, injectable, and noncanonical IDs. Assert all
      snapshot levels reject mutation; changing original input lists/dicts does not
      alter observations. Seven canonical unique weekdays are required. Check JSON
      output includes UTC timestamp, complete/retry_required, raw values, and slots.
      Assert missing/inactive/code261/unknown errors request retry, code7 and
      unsupported format alone do not, and only readable/empty days are complete.
- [ ] **Step 5: Observe RED, implement the response models and private frozen
      metadata specialization, then rerun the model tests.** Expected: GREEN.
- [ ] **Step 6: Run** `uv run pytest -n 4` and
      `uv run ruff check src/bsblan/schedules.py tests/test_unified_schedule_models.py`.
      Expected: full suite and checks pass. Commit only this task's files with
      `feat: add shared immutable schedule types`.

### Task 2: Configure mappings once and unify schedule reads

**Files:** Modify `bsblan.py`, `_schedules.py`, `__init__.py`, and schedule read
regressions; create `tests/test_unified_schedules.py`.

**Interfaces:**

- Consumes Task 1 types from `bsblan.schedules`.
- Adds `BSBLANConfig.schedule_mappings: ScheduleMappings` with an empty default.
- Produces `BSBLAN.hot_water_schedule() -> ScheduleSnapshot` and
  `BSBLAN.heating_schedule(*, circuit: int = 1) -> ScheduleSnapshot`.
- Produces internal `ScheduleManager.read(kind, circuit=None) -> ScheduleSnapshot`
  and one resolver shared with Task 3; no per-call mappings or include filters.
- `BSBLANScheduleMappingError` retains kind, circuit, and reason for both reads
  and writes. Existing client initialization requests remain independent.

- [ ] **Step 1: Add failing HTTP-boundary read tests.** Configure each group with
      unrelated literal IDs and verify seven-ID query strings, exact-key day mapping
      despite shuffled responses, group/client isolation, fresh second reads, and
      no factory-reset ID. Empty objects return seven missing days; code7/261 entities
      retain metadata. A valid day survives a different day's unsupported text.
- [ ] **Step 2: Run** `uv run pytest --no-cov -n 0 tests/test_unified_schedules.py -k read`.
      Expected: RED for the new configuration/read contract.
- [ ] **Step 3: Wire immutable config into ScheduleManager and implement reads.**
      Revalidate unchecked pydantic constructions before I/O, copy input metadata,
      call the Task 1 parser, and classify unsupported text as `unparsed`. Keep
      malformed entities and envelopes contextual typed exceptions.
- [ ] **Step 4: Add failing negative tests.** Unknown mapping, unchecked malformed
      mapping, bool/float/invalid circuit, and known PPS send no schedule requests.
      A client without schedule configuration still reads ordinary climate state.
      Invalid JSON preserves its original decode cause/location; programming errors
      are not relabeled; no negative availability cache prevents recovery.
- [ ] **Step 5: Observe RED, implement guards, and migrate old read tests.** Replace
      raw schedule assertions with structured observations; preserve generic raw
      reads and non-/JQ endpoint behavior in transport tests. Do not discard legacy
      malformed-envelope/recovery tests merely because API names changed.
- [ ] **Step 6: Run** `uv run pytest -n 4`. Expected: GREEN, including model and
      transport regressions. Commit `refactor: unify configured schedule reads`.

### Task 3: Mapping-consistent, acknowledged, partial schedule writes

**Files:** Modify `_schedules.py`, `bsblan.py`, `exceptions.py`, `__init__.py`, both
existing setter test modules, and `tests/test_unified_schedules.py`.

**Interfaces:**

- Consumes Task 1 `ScheduleUpdate` and Task 2 mapping resolver.
- Produces both setter signatures from the spec and internal
  `ScheduleManager.write(kind, update: ScheduleUpdate, circuit=None) -> None`.
- Produces `BSBLANScheduleWriteError(kind, circuit, acknowledged_days,
failed_day, parameter_id, unattempted_days, outcome)`; weekday collections
  are tuples, outcome is `rejected` or `unknown`, transport cause is chained.

- [ ] **Step 1: Add failing real-HTTP write tests.** Read Tuesday from synthetic
      ID `700.1`, update only Tuesday, and assert /JS writes `700.1`, never fixed
      `502`. Test DHW, both circuits, canonical day order, and one request per day.
      Only `{requested_id: {"status": 1}}` acknowledges a write.
- [ ] **Step 2: Run** `uv run pytest --no-cov -n 0 tests/test_unified_schedules.py -k write`.
      Expected: RED for the new shared mapping/acknowledgement contract.
- [ ] **Step 3: Prevalidate the entire update, serialize all commands, and send
      sequentially through the existing transport.** Inspect the response directly;
      `_set_device_state()` currently discards it and cannot prove acknowledgement.
      Do not change thermostat or non-schedule hot-water write behavior.
- [ ] **Step 4: Add failing safety tests.** An invalid later day, empty update,
      snapshot-as-update, missing mapping, read-only bus, known PPS, or requested
      clear prevents every write. Cover status 0, missing key, string/bool status,
      malformed/nonobject response, and generic `{"status":"ok"}` rejection. Test
      two-day writes where the second is rejected or times out: acknowledged days,
      failed ID, unattempted days, uncertainty, and cause remain observable; later
      days are never sent. Cancellation propagates and never resumes the week.
- [ ] **Step 5: Observe RED and implement the error/progress contract.** Keep
      transport retries bounded as before and avoid claiming rollback or readback.
      Reject empty-day clears before any /JS call until a real-device clear encoding
      is independently confirmed. Migrate setter fixtures away from generic success.
- [ ] **Step 6: Run** `uv run pytest -n 4`. Expected: GREEN. Commit
      `feat: acknowledge mapped schedule writes and report partial failures`.

### Task 4: Remove alternate schedule APIs and reconcile error contracts

**Files:** Modify `models.py`, `_hot_water.py`, `constants.py`, `__init__.py`,
`bsblan.py`, `exceptions.py`, `openspec/specs/error-classification/spec.md`, and
all tests importing removed schedule types (including `test_dhw_time_switch.py`,
`test_constants.py`, and hot-water group tests).

**Interfaces:**

- Produces the final exports: Task 1 types and mapping/write errors; no old
  get/raw reader aliases or target-specific schedule payload classes.
- `SetHotWaterParam` no longer accepts `dhw_time_programs`; non-schedule fields
  and `set_hot_water()` semantics are unchanged.
- Generic parameter reads remain the raw diagnostic escape hatch.

- [ ] **Step 1: Add failing behavioral tests around alternate entry points.**
      Passing the removed schedule field to `SetHotWaterParam` cannot send a write;
      non-schedule hot-water calls still work. Generic parameter access still returns
      the requested raw TIMEPROG value. Exercise unknown mappings without requiring
      unrelated hot-water validation or mutating availability caches.
- [ ] **Step 2: Run the focused tests; expected RED while the bypass exists.**
- [ ] **Step 3: Remove old definitions, private schedule fetches, raw write
      branches, schedule-only constants/groups, and duplicate exports.** Update
      remaining imports to the shared module. Preserve general parameter mappings
      if generic named reads still use them; do not remove unrelated IDs or fields.
- [ ] **Step 4: Replace obsolete tests with equivalent unified contract coverage.**
      Keep observable absence/error/recovery cases, not tests of removed aliases.
      Update the OpenSpec contract: incomplete observations are values, unparsed
      text is not corrupt JSON, unsupported configured operations fail locally, and
      exception types alone do not promise recovery/permanence.
- [ ] **Step 5: Run** `uv run pytest -n 4` and `uv run ty check`.
      Expected: GREEN. Commit `refactor: remove legacy schedule paths`.

### Task 5: Read-only example, migration guide, and final verification

**Files:** Create `examples/read_schedules.py`,
`tests/test_read_schedules_example.py`, and `docs/schedule-migration.md`; modify
README, getting-started, API docs, and `examples/control.py`. Replace the related
untracked `tests/test_control_example.py` with appropriate read-only CLI tests.

**Interfaces:**

- CLI: `read_schedules.py --hot-water-mapping JSON --heating-mapping JSON
--circuit {1,2}`; at least one mapping required, invalid input rejected before
  discovery/network. Omitted mappings skip their group; no write mode exists.
- Consumes only Task 2 readers and frozen snapshot JSON serialization.
- Migration guide documents every removed symbol, new config shape, partial
  write outcomes, unsupported-clear restriction, and dependent HA plan.

- [ ] **Step 1: Add failing CLI tests.** Execute parser/entry point with controlled
      discovery and synthetic HTTP; malformed/missing mappings fail before I/O.
      Valid DHW-only/heating-only/both cases print all observed outcomes. Capture
      requested HTTP paths and fail on any /JS call. `control.py --circuit 2` must
      fail argument validation rather than run default-circuit writes.
- [ ] **Step 2: Observe RED, implement the separate read-only example, and remove
      schedule CLI/read/write additions from control.py.** Remove its legacy
      automatic DHW schedule write because its payload path no longer exists.
- [ ] **Step 3: Update documentation and API members.** Show only synthetic or
      placeholder mappings, never label fixture IDs universal. Explain disabled
      schedules without mappings, read-only inspection, stale/incomplete values,
      acknowledgement versus verification, and clear/write safety gates.
- [ ] **Step 4: Run** `uv run pytest --cov=src/bsblan --cov-report=term-missing -n 4`.
      Expected: all tests pass, total >=95%, modified executable lines fully covered.
- [ ] **Step 5: Run** `uv run prek run --all-files`, then rerun the full tests if
      any hook modifies code. Inspect every hook-generated diff; exclude unrelated
      changes. Expected: all required hooks pass and `git diff --check` is clean.
- [ ] **Step 6: Perform a separate whole-branch self-review against the spec and
      Review Focus (no subagent tool available).** Fix important findings through
      failing-test/implementation/full-suite cycles. Record limitations and any
      decisions in the execution ledger. Commit `docs: document unified schedule API`.

## Plan self-review

- Spec coverage: mapping ownership, immutable observations, shared parsing,
  preflight validation, acknowledgement/uncertainty, bypass removal, CLI safety,
  and error/docs migration each have an owning task.
- Interface scan: Tasks 2/3 consume the same Task 1 types and mapping resolver;
  Task 4 removes the old exports only after the consumers have migrated.
- Review Focus: each of the five failure classes has explicit test coverage in
  its named task, not just a final manual-review reminder.
- Scope: the HA migration is a dependent separate plan; no speculative release
  pin or modifications to the shared HA checkout are required by this plan.
- Safety decision: empty-day intent remains representable, but actual clearing
  is locally rejected until the device's accepted encoding is verified.

## Handoff and completion

- [ ] Deliver library branch, test/hook evidence, migration document, and the
      dependent `2026-11-13-ha-unified-schedules.md` plan.
- [ ] Do not label the library release-ready before the HA plan passes against
      the new package. No confirmed profile or device clear fixture currently
      exists; do not claim device validation.
- [ ] Keep original checkout and unrelated user work intact; no push or release.
