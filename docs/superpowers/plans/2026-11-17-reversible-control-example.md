# Reversible Control Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make control.py read-only by default and reversible for thermostat/mode/schedule demos.

**Architecture:** A typed example-only helper preflights saved originals and performs one guarded write/readback/restore/readback roundtrip at a time. The existing display script gains a validated CLI and routes all circuit-dependent calls consistently.

**Tech Stack:** Python 3.12+, asyncio, argparse, dataclasses, existing bsblan models, pytest.

**Spec:** `docs/superpowers/specs/2026-11-17-reversible-control-example-design.md`

## Global Constraints

- Python 3.12+, no new dependencies or library behavior changes.
- Preserve all prior uncommitted work; no live-device access during development.
- All writes require `--write`; time sync is intentionally not restored.
- Confirmed mappings only; one selected nonempty, restorable schedule day per run.
- Keep changes on the feature branch without committing, pushing or merging.

## Review Focus

- An uncertain write may have applied and must still arm restoration.
- Failed readback and failed restoration must not hide either failure.
- Circuit 2 selection must never silently write thermostat circuit 1.
- Empty/unparsed/unavailable originals cannot be safely restored and must block all writes.
- Read-only/default/invalid CLI paths must never mutate temperature, mode, schedules or time.

### Task 1: Reversible example helper

**Files:** Create `examples/control_roundtrip.py`, `tests/test_control_roundtrip.py`.

**Interfaces:** Immutable `ControlOptions`; `run_roundtrip(client: BSBLAN, options: ControlOptions) -> None`; public API reads/writes only. One generic helper performs apply/verify/finally-restore/verify.

- [x] Write failing tests for preflight ordering, selected circuit/day/group, temperature/mode restoration, nonempty original schedule restoration and skipping equal targets.
- [x] Run focused tests and observe missing functionality.
- [x] Implement example-only options, preflight and roundtrips without touching library code.
- [x] Add failing tests for missing/error/readonly/nonfinite originals, known bounds, PPS modes, uncertain writes, failed readbacks, cancellation and combined restoration errors.
- [x] Implement failure handling; run focused tests to green.

### Task 2: CLI and main integration

**Files:** Modify `examples/control.py`, `tests/test_read_schedules_example.py`; create `tests/test_control_example.py`.

**Interfaces:** `parse_options(argv: list[str] | None = None) -> ControlOptions`; `main(options: ControlOptions) -> None`. Flags: `--write`, `--circuit`, `--temperature`, `--hvac-mode`, mutually exclusive confirmed mappings, `--weekday`, `--schedule`.

- [x] Write failing CLI/main tests for read-only defaults, invalid arguments before discovery, explicit-write gating, both supported circuits and one schedule group.
- [x] Implement validated options and integrate helper while preserving existing display functions.
- [x] Retain supported local time sync only after successful reversible changes and only with `--write`.
- [x] Replace the superseded circuit-flag rejection test with invalid-circuit rejection and verify selected-circuit routing.
- [x] Run focused and full pytest; test `control.py --help` without device contact.

### Task 3: Documentation and final verification

**Files:** Modify `docs/getting-started.md`, `docs/schedule-profiles.md`, `README.md`; update example module documentation.

- [x] Document safe invocation, native temperature units, explicit mapping/day/interval, readback/restore behavior and intentionally persistent time sync.
- [x] Review cancellation/partial-failure behavior and clearly state restoration limitations and no concurrent automation safety guarantee.
- [x] Run focused example safety tests and full pytest, required all-files hooks, targeted formatting, strict docs build and whitespace checks. The user explicitly waived example-script coverage targets; do not pursue them.
- [x] Record results and leave user files and existing feature work intact.

## Verification results

- 73 focused helper/CLI/read-schedule tests passed, including failure-path restoration; no example coverage target was applied.
- `uv run pytest -q`: 1002 passed; existing library coverage remains 100%.
- `uv run prek run --all-files`: passed; non-applicable hooks skipped.
- Changed Markdown formatted directly with the installed Prettier binary.
- `uv run python examples/control.py --help`: passed without discovery or writes.
- Strict MkDocs build and `git diff --check`: passed.
- No live-device access; all write tests use an in-memory client. Existing uncommitted feature work and unrelated user files remain intact.
