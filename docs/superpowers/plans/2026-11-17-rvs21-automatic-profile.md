# RVS21 Automatic Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable evidence-backed default discovery and a reversible live schedule test without manual mappings.

**Architecture:** Add declarative per-profile active-layout signatures to the existing resolver, seed the first supported profile with sanitized source/device evidence, and route the control example's schedule target through automatic selection.

**Tech Stack:** Python 3.12+, pydantic, asyncio, existing aiohttp transport, pytest.

**Spec:** `docs/superpowers/specs/2026-11-17-rvs21-automatic-profile-design.md`

## Global Constraints

- Exact observed controller/build/bus/destination scope; no guessed scans or firmware-only selection.
- No import/startup probes, sleeps, background work or permanent negative caches.
- Preserve explicit overrides, parameter permission checks and fresh write preflight.
- No credentials, MAC, IP or current program values in committed fixtures.
- No example coverage target; no commits, pushes or sibling firmware modifications.

## Review Focus

- An inconclusive candidate must prevent selecting a competing profile by order.
- Missing/wrong structure fields must not enable an unknown layout.
- Previously observed table changes must invalidate cached mappings.
- A missing DHW group must not disable verified HC1.
- The example must use the automatic group consistently for reads, writes and restore.

### Task 1: Declarative table matching and first profile

**Files:** Modify `src/bsblan/schedule_profiles.py`, `src/bsblan/_schedule_profiles.py`; create `tests/test_standard_schedule_profiles.py`, `tests/fixtures/rvs21_schedule_profile.json`; adjust explicit-empty-registry tests.

**Interfaces:** `ScheduleProfile.table_parameters: tuple[tuple[str, str], ...]`; exact first standard profile. Resolver compares group structures before reading values and records a layout revision in its identity key.

- [x] Write failing tests for default selection without mappings/table assertion, exact scope, signature validation and source-backed mapping IDs.
- [x] Implement declarative signatures and first built-in entry, retaining explicit-table behavior for existing profiles.
- [x] Add failing tests for incomplete/malformed/wrong structures, independent groups, ambiguity, retries, explicit assertion conflicts and layout-change invalidation.
- [x] Implement scoped read-only table matching and per-call probe reuse.
- [x] Run focused and full pytest; update only tests whose empty-default assumption is intentionally superseded.

### Task 2: Automatic control example

**Files:** Modify `examples/control.py`, `examples/control_roundtrip.py`, `tests/test_control_example.py`, `tests/test_control_roundtrip.py`.

**Interfaces:** `ControlOptions.schedule_kind`; `--schedule-group {heating,hot-water}`. A nonempty `--schedule` without manual mapping selects automatic heating by default; all writes still require `--write`.

- [x] Write failing parser/routing tests, including no manual mappings in automatic configuration and consistent DHW/heating read/write/restore.
- [x] Implement automatic selection while preserving default no-schedule I/O and manual precedence.
- [x] Run focused tests and full suite; no script coverage gate.

### Task 3: Documentation, verification and authorized live test

**Files:** Update user/API guides and mark earlier empty-registry/table-only descriptions as superseded.

- [x] Document supported exact profile scope, source provenance, signature guarantees/limitations, retry behavior and automatic CLI use.
- [x] Run required all-files hooks, full coverage, targeted formatting, strict docs build and whitespace checks.
- [x] On the real board, use default discovery/read/write APIs without a manual mapping; back up all HC1 days, change Tuesday only, restore in finally and independently verify the full week and thermostat originals.
- [x] Delete temporary credentials and record test results without secrets.

## Verification results

- Full pytest: 1101 passed, 100% measured library statement/branch coverage; no example coverage target.
- Required all-files hooks, direct Markdown/JSON formatting, strict documentation build and whitespace checks passed.
- Default live discovery selected `rvs21-211-127-integer-20251124` for HC1 and DHW; HC2 stayed unknown. No manual mappings or table assertion were supplied.
- Real example parser/main ran a single HC1 day roundtrip. Audited requests confirmed exactly two acknowledged schedule writes to parameter 502, followed by permitted time sync; no other weekday or thermostat writes.
- Fresh-client verification confirmed all seven parsed and raw HC1 days restored, and thermostat setpoint/mode unchanged.
- Protected temporary credentials were deleted after successful independent verification. Raw baseline/result journals remain user-only temporary files, not repository fixtures.
- Sibling firmware source and user files were not modified; changes remain uncommitted on the feature branch.
