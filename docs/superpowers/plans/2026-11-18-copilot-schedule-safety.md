# Copilot Schedule Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address the three verified Copilot findings on PR #1678 with regression tests and no live-device writes.

**Architecture:** Preserve fresh layout metadata alongside value-probe results and combine permission evidence with deny priority. Add a task-local transport-attempt guard for schedule commands, including retries, without changing request payloads. Validate/encode updates before automatic network resolution.

**Tech Stack:** Python 3.12+, asyncio/contextvars/contextlib, existing aiohttp/backoff/pydantic/pytest.

**Spec:** Existing verified-profile and reversible-control specs, plus Copilot review 5955635341 on PR #1678.

## Global Constraints

- Retain the rebased PR head and dependency update; never force-push or merge old duplicate history.
- No live board access, new dependencies or rule suppressions.
- Explicit permission denial from either fresh source wins; never cache permission proofs for writes.
- Revalidate transport target and relevant metadata/proof before every actual attempt, including retry backoff exits.
- Profile-generation guards apply to automatic mappings; manual overrides remain independent of profile-cache invalidation.
- Preserve no-op/clear/input errors locally, partial-write reporting, normal bounded retries and unrelated requests.
- Keep unrelated user directories untouched and do not impose example coverage targets.

## Review Focus

- `/JC` denial plus absent or affirmative `/JQ` permission must block all writes.
- Successful cached discovery must not reuse stale structure permissions during a later write.
- A single-day retry must not follow changed host, port, passkey, bus destination, generation or gateway permission state.
- Attempt guards must be reset after failures/cancellation and isolated from other requests/tasks/clients.
- Malformed, empty or clear updates must fail before any automatic discovery I/O.

### Task 1: Preserve fresh structure permissions

**Files:** `_schedule_profiles.py`, `_schedules.py`, regression tests in `tests/test_copilot_schedule_safety.py`.

- [x] Reproduce discarded-layout-denial behavior with `/JC` flags 1/2, absent/conflicting `/JQ` flags and enabled defaults.
- [x] Carry fresh layout responses through resolution, combine flags with denial priority, and keep cached resolutions free of response/permission data.
- [x] Verify explicit layout allowance works under disabled defaults and permission changes are re-probed on each write.

### Task 2: Guard every transport attempt

**Files:** `_transport.py`, `_schedules.py`, `bsblan.py`, retry regression tests.

- [x] Reproduce retargeting during real backoff with mocked HTTP only, including successful second responses that must never be reached.
- [x] Add a per-transport ContextVar guard context, invoked before building each request/retry destination.
- [x] Bind schedule write proof to the callback, checking target, relevant metadata/generation and permissions on every attempt; retain outer checks for mocked facades.
- [x] Verify safe retries still succeed and guards cannot leak to unrelated requests or concurrent tasks.

### Task 3: Validate before resolution; publish review updates

- [x] Reproduce invalid automatic updates initiating I/O; validate/reconstruct/encode all populated days before awaiting resolution.
- [x] Run focused/full tests, required all-files hooks, strict docs build and whitespace checks; preserve coverage and Sonar quality.

Local validation before publication: 1132 tests passed with 100% measured library
statement/branch coverage; required hooks, Ruff/ty, strict docs build and diff
checks passed. Remote analysis results are checked after publication. No live
board writes or example coverage target were used for this review follow-up.

- [ ] Commit/push the fixes to the existing PR, reply to each finding with evidence, resolve addressed threads and update the PR body.
- [ ] Verify the new revision's GitHub/Sonar checks and record results.
