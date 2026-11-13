# Home Assistant Unified Schedules Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate HA's BSB-LAN schedule consumers to the unified library without
changing entity/action identities or merged setpoint and targeted-refresh behavior.

**Architecture:** HA provides per-entry confirmed mappings, constructs the common
partial update type, and owns refresh/retry/publication. Unconfigured schedules
are disabled independently of climate monitoring. This plan depends on the
completed library plan and executes in a separate HA worktree, not HA's shared
`dev` checkout.

**Tech Stack:** Current HA development Python/environment, pytest and existing HA
fixtures/selectors/config flows, locally built python-bsblan during development.
No runtime dependency other than the new python-bsblan release is introduced.

**Spec:** `docs/superpowers/specs/2026-11-13-unified-schedules-design.md` in the
library repository. Prerequisite plan:
`docs/superpowers/plans/2026-11-13-unified-schedules.md`.

## Global Constraints

- Python 3.12+; use uv and the existing dependencies only. HA's higher current
  minimum Python version also applies in the HA workspace.
- Treat API v3 as the supported baseline; do not reintroduce v1-only behavior.
- Response/state models use pydantic.BaseModel.
- Set-parameter payload models use @dataclass.
- Parameter names use snake*case; preserve dhw*_ and legionella*function*_ names.
- Send one /JS request per populated day, sequentially.
- No automatic discovery, guessed IDs, firmware-only profile selection, or live
  device writes during development.
- Unknown schedule mappings disable schedules, not ordinary climate monitoring.
- Keep total coverage at 95%+ and patch coverage at 100%.
- Run uv run prek run --all-files before finishing implementation changes in the
  library. Use HA's own required checks for the HA workspace.
- Preserve unrelated dirty files and untracked plans/OpenSpec work.
- Preserve entity IDs, device identifiers, action names, existing action schema,
  active/configured setpoint semantics, temporary overrides, and poll scheduling.
- No push, shared-branch merge, dependency publication, or speculative version pin.

## Review Focus

- An incomplete snapshot must not clear refresh-pending state as if the week
  were complete; Task 2.
- A stale refresh finishing after a newer write must not consume that write's
  refresh generation; retain generation guards in Task 2.
- Schedule options absent/invalid must not prevent climate setup; Task 1.
- A partial/uncertain write must still trigger readback and retain service error
  context; Task 3.
- A mapping for the old host must not silently follow target reconfiguration;
  clear it on target change in Task 1.

## Workspace and baseline

- [ ] Obtain consent for an isolated HA worktree/branch. Start from current
      upstream `dev`, including merged #187891/#188197/#187892/#187852/#181360 and
      #176294. Do not start from local `910c1f15ec6` without updating the baseline.
- [ ] Read the HA repository's current agent/contributor instructions before any
      changes. Re-read integration files and tests from that exact baseline.
- [ ] Run baseline `pytest -q tests/components/bsblan` with HA's documented setup.
- [ ] Build/install the new library locally only in this isolated environment.
      Record the package commit and test command; no requirement-file path override
      or unpublished version may be committed as a release pin.

## File structure

All paths below are relative to the HA repository.

| Path                                             | Responsibility                                                          |
| ------------------------------------------------ | ----------------------------------------------------------------------- |
| `homeassistant/components/bsblan/config_flow.py` | Optional confirmed mapping JSON options                                 |
| `homeassistant/components/bsblan/const.py`       | New options key only; existing action enums unchanged                   |
| `homeassistant/components/bsblan/__init__.py`    | Construct client configuration and disable unconfigured schedule groups |
| `homeassistant/components/bsblan/coordinator.py` | Shared snapshot types and outcome-aware pending refresh                 |
| `homeassistant/components/bsblan/services.py`    | Shared update payload and partial-failure refresh                       |
| `homeassistant/components/bsblan/diagnostics.py` | JSON-mode snapshot serialization                                        |
| `homeassistant/components/bsblan/strings.json`   | Mapping instructions, invalid mapping and write errors                  |
| `tests/components/bsblan/`                       | Config, services, diagnostics, startup, and merged-feature regressions  |

---

### Task 1: Optional mapping configuration without climate setup dependency

**Interfaces:**

- Add `CONF_SCHEDULE_MAPPINGS = "schedule_mappings"`; store a validated JSON object
  compatible with `ScheduleMappings.model_dump(exclude_none=True)` in entry options.
- Add `BSBLanOptionsFlow.async_step_init(user_input=None)` and register the
  options flow using the current HA API. The user-facing field is optional
  multiline JSON text; empty text clears mappings. Validate with the library
  model, return field error `invalid_schedule_mappings`, and make no device I/O.
- Feed validated options into `BSBLANConfig.schedule_mappings` at setup.

- [ ] Add failing config-flow/setup tests: absent options load normal climate;
      valid DHW/heating JSON persists per entry/group; invalid/missing/duplicate IDs
      stay on the form without I/O; empty text disables schedules. Invalid persisted
      mapping options disable schedules with one actionable warning, not all setup.
- [ ] Run `pytest -q tests/components/bsblan/test_config_flow.py
tests/components/bsblan/test_init.py`; expect RED for the new options contract.
- [ ] Implement the field, model validation, update/reload listener and setup
      wiring. Explain that users must independently confirm the active target/table
      and each weekday; firmware/name/value types are not evidence of day assignment.
- [ ] Add and observe failing reconfiguration tests: changing host/port removes
      stored mappings and requires reconfirmation; credential-only reauthentication
      does not erase mappings. Never change entry/entity/device identifiers.
- [ ] Implement target-change invalidation, rerun focused tests and all BSB-LAN
      tests; expect GREEN. Commit `feat: configure confirmed BSB-LAN schedule mappings`.

### Task 2: Outcome-aware schedule refresh and diagnostics

**Interfaces:**

- `BSBLanSlowData.dhw_schedule: ScheduleSnapshot | None` and
  `heating_schedule: dict[int, ScheduleSnapshot]` replace old response types.
- `_async_fetch_dhw_schedule()` and `_async_fetch_heating_schedule(circuit)` keep
  their tuple result shape; derive retryability from `snapshot.retry_required`.
- Disabled groups are not queued for requests. Diagnostics use
  `snapshot.model_dump(mode="json")`.

- [ ] Add failing coordinator tests for complete, missing, unparsed, code7,
      code261, and malformed-envelope results. Assert transient incomplete outcomes
      remain pending, unsupported-format-only outcomes do not endlessly retry, and
      newer observations expose unavailable days rather than disguising stale ones.
- [ ] Run `pytest -q tests/components/bsblan/test_services.py
tests/components/bsblan/test_init.py tests/components/bsblan/test_diagnostics.py`;
      expect RED against the old model/retry behavior.
- [ ] Adapt read helpers and pending logic, preserving refresh generation guards,
      nonblocking startup, and slow polling intervals. Publish structured incomplete
      snapshots explicitly; if values are retained elsewhere they must remain
      labeled stale, not newly confirmed by the incomplete response.
- [ ] Update diagnostic fixtures/snapshots. Test unknown mappings cause no
      schedule I/O while normal fast/slow state remains functional. Retain the
      overlapping-write/refresh-generation regressions.
- [ ] Run the complete BSB-LAN suite; expect GREEN. Commit
      `refactor: consume structured BSB-LAN schedule observations`.

### Task 3: Shared service payloads and truthful write outcomes

**Interfaces:**

- Existing action handlers construct `ScheduleUpdate(**days)` rather than
  `DHWSchedule`/`HeatingSchedule`; action names, targets, weekday fields, and
  omitted-day semantics remain unchanged.
- Preserve the existing `finally` refresh behavior after attempted writes.
- Translate absent mappings, unsupported clearing, and
  `BSBLANScheduleWriteError` into actionable existing HA service exception forms.

- [ ] Add failing action tests: unchanged target validation, only supplied days
      in the update, explicit empty-day intent rejected clearly until verified,
      wrong-target profiles not reused, and no whole-week replacement.
- [ ] Add failing partial/uncertain write tests: preserve acknowledged/failed day
      context in the error, refresh even after an exception, and retain latest
      refresh-generation state. Acknowledgement must not become optimistic state.
- [ ] Run `pytest -q tests/components/bsblan/test_services.py`; expect RED.
- [ ] Adapt payload construction/error translation, preserving schemas and
      refresh ownership. Do not add a generic active-temperature setter or alter
      climate/water-heater/setpoint-number write selection.
- [ ] Run the complete BSB-LAN suite; expect GREEN. Commit
      `refactor: migrate BSB-LAN schedule actions to shared updates`.

### Task 4: Integration regression and coordinated release gate

**Interfaces:** Consumes all prior tasks and the completed library branch.

- [ ] Run the current upstream regression tests for active climate/DHW setpoints,
      equal setpoints, automatic/permanent modes, temporary overrides, number entity
      validation, targeted circuit/DHW refresh, failed readback, preserved poll
      schedule, and running-poll serialization. Add missing integration coverage
      before fixing any regression; do not rewrite intended merged behavior.
- [ ] Run `pytest -q tests/components/bsblan` against the new library, HA Ruff/type
      checks, `python -m script.hassfest --integration-path
homeassistant/components/bsblan`, and HA's generated-file checks as documented
      by the checked-out baseline. Record the exact outputs and Python version.
- [ ] Perform a separate whole-change review, including the still-open PPS PR's
      capability interaction. Do not cherry-pick stale PPS hunks into removed
      `async_set_data()` code; any PPS rebase is a separately reviewed change.
- [ ] Prepare user-facing migration/release notes for optional confirmed mappings
      and the clear-operation restriction. Coordinate documentation outside Core
      separately; do not claim new profiles or clear encodings were hardware tested.
- [ ] Only after a real library release is authorized and exists, update the
      manifest/derived requirement files to that exact released version and rerun
      the suite. Until then, deliver a tested local migration branch, not a fictional
      release pin. No publish/push action is authorized by this plan.

## Completion

The library change and this migration must be reviewed together. Missing mapping
configuration intentionally disables schedule operations; it must not disable
ordinary climate monitoring. Full hardware schedule support and clearing remain
unverified without installation-specific evidence.
