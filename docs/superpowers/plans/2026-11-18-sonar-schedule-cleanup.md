# Sonar Schedule Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve PR #1678's 24 maintainability findings without changing schedule behavior.

**Architecture:** Isolate exception-test setup, then extract small pure classification helpers and explicit sequential control flow from the existing resolver, table matcher and permission preflight. Keep network request order, exception classes, cache guards and retry priority unchanged.

**Tech Stack:** Python 3.12+, existing pytest/pydantic/aiohttp tooling, SonarCloud API.

**Spec:** Existing behavior and safety constraints in `docs/superpowers/specs/2026-11-17-rvs21-automatic-profile-design.md` and the operator-approved Sonar review from 2026-11-18.

## Global Constraints

- No new features, dependencies, suppressions or live-device writes.
- Preserve ASCII-only controller numbers; use `re.ASCII` with any digit shorthand.
- Preserve sequential awaited resolution; do not feed an async generator to `tuple()`.
- Preserve incomplete-before-incompatible priority, malformed/transport exceptions and permission proof checks.
- No example coverage target; keep library total >=95% and changed executable lines covered.
- Leave unrelated `openspec/` and `plans/` files untouched; operator authorized commits and push to the existing branch.

## Review Focus

- An exception must originate from the tested operation, not argument construction.
- Unicode digit lookalikes must not match a supported numeric controller identity.
- Concurrent bus queries must not replace the sequential awaited loop.
- Partial/incompatible candidates and table rows must keep their original result priority.
- Permission structure checks must still precede every possible write and reject stale proof.

### Task 1: Clarify exception tests

**Files:** `tests/test_control_example.py`, `tests/test_control_roundtrip.py`, `tests/test_schedule_profile_integration.py`.

- [x] Move setup/constructors outside the 13 reported `pytest.raises` blocks, leaving one tested invocation in each.
- [x] Run focused tests and check the diff has no changed expectations or behavior.
- [x] Commit the test-only cleanup.

### Task 2: Simplify resolver and preflight code

**Files:** `src/bsblan/_schedule_profiles.py`, `src/bsblan/_schedule_tables.py`, `src/bsblan/_schedules.py`, regression tests in `tests/test_schedule_profiles.py`.

- [x] Pin Unicode rejection and sequential eager tuple resolution with regression tests; run them against current code before refactoring.
- [x] Extract controller-field/identity validation and profile-candidate selection helpers, replacing nested status expressions with guard clauses.
- [x] Replace the awaited comprehension with an explicit sequential accumulation loop; use ASCII-flagged digit shorthand.
- [x] Extract per-row table classification and per-entity permission classification/fetching to bring each function below Sonar's cognitive complexity threshold.
- [x] Run focused/full tests and required `uv run prek run --all-files`, then commit the source cleanup.

### Task 3: Push and verify Sonar

- [x] Run full pytest, strict docs build and diff checks; confirm unrelated user files unchanged.
- [ ] Push normally to `feat/verified-schedule-profiles`, without force or merging.
- [ ] Check the new PR analysis revision and issue count through SonarCloud; report any remaining findings honestly.
