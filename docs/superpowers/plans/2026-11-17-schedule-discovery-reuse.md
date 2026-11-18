# Schedule Discovery Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce slow-bus discovery traffic and provide a safe read-only #1668 diagnostic.

**Architecture:** The existing schedule manager owns a positive mapping cache, generation guard and profile-work lock. The resolver remains the source of fresh evidence/probes and offers a bounded diagnostic using the same compatibility classifier.

**Tech Stack:** Python 3.12+, asyncio, pydantic, aiohttp, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-11-17-schedule-discovery-reuse-design.md`

## Global Constraints

- Python 3.12+, API v3 baseline, no new dependencies or HA Core changes.
- Keep the standard profile registry empty pending independently reviewed installation scope.
- Preserve caller-confirmed overrides and all existing write safety gates.
- No sleeps, background tasks, automatic fallback scans or negative caches.
- Keep all existing uncommitted work and unrelated user files intact; do not push or merge.

## Review Focus

- An invalidation during an await must not republish the invalidated proof.
- Cache reuse must never reuse schedule values or bypass fresh write preflight.
- Concurrent/cancelled discovery must release locks without storing partial trust.
- A compatible diagnostic candidate must never enable a schedule group.
- Timeouts and transient data must not start fallback scans or mapping repairs.

### Task 1: Reusable validated profiles

**Files:** Modify `src/bsblan/_schedules.py`, `src/bsblan/_schedule_profiles.py`, `src/bsblan/bsblan.py`; create `tests/test_schedule_profile_cache.py`; adjust the existing repeated-read expectation in `tests/test_schedule_profile_integration.py`.

**Interfaces:** `discover_schedules(*, refresh: bool = False) -> tuple[ScheduleAvailability, ...]`, `invalidate_schedule_profiles() -> None`. Manager caches only successful resolutions with response data removed. Resolver exposes shared compatibility classification for fresh cached reads.

- [x] Write failing tests for discovery priming, fresh subsequent values, refresh, explicit/metadata/connection invalidation and no negative caching.
- [x] Run focused tests and observe missing APIs/excess identity requests.
- [x] Implement positive cache, lock, generation guard and fresh cached-read compatibility checks.
- [x] Add failing race/cancellation tests, fresh preflight on cached writes and invalidation between sequential commands.
- [x] Wire exhausted transport connection failures to synchronous cache invalidation; preserve existing exception classes.
- [x] Run focused and full pytest; retain all manual schedule behavior.

### Task 2: Issue #1668 bounded diagnostic

**Files:** Modify `src/bsblan/schedule_profiles.py`, `src/bsblan/_schedule_profiles.py`, `src/bsblan/_schedules.py`, `src/bsblan/bsblan.py`, `src/bsblan/__init__.py`; create `tests/test_schedule_candidate_probe.py`.

**Interfaces:** `ScheduleCandidateProbe`; `probe_schedule_candidate(candidate_id: str) -> ScheduleCandidateProbe`. The only supported ID is `issue_1668_dhw`; proposed IDs are exactly `561,561.1,561.2,561.3,561.4,561.5,561.6`.

- [x] Write failing tests for exact read-only requests, unknown IDs, compatible-but-disabled results and immutable candidate provenance.
- [x] Implement the opt-in probe, explicit bus checks and shared compatibility outcomes including per-parameter failure IDs.
- [x] Add retry/auth/malformed/PPS/target-change and real HTTP tests; assert no automatic fallback or cache promotion.
- [x] Add a regression showing a separately confirmed manual override writes Tuesday/Sunday to `561.1`/`561.6`, never integer weekday IDs.
- [x] Run focused and full pytest.

### Task 3: Consumer guidance and final verification

**Files:** Modify `docs/schedule-profiles.md`, `docs/getting-started.md`, `docs/schedule-migration.md`, `docs/api/client.md`, `docs/api/models.md`, `README.md`.

**Interfaces:** Document cache lifetime/invalidation, fresh writes, diagnostic-only candidate status and HA-controlled deferred discovery.

- [x] Document an integration scheduling sketch with a >=15-second post-initial-read delay, polling coordination, unload cancellation and retry handling; clearly label it guidance rather than HA code shipped here.
- [x] Update prior descriptions that automatic reads always re-identify; explain unreported remote-change limitations and the empty standard registry.
- [x] Review the complete follow-up diff and add missing edge-case tests.
- [x] Run full coverage, `uv run prek run --all-files`, targeted Prettier, strict MkDocs build and whitespace checks.
- [x] Record results and leave all changes on the existing feature branch, uncommitted.

## Verification results

- `uv run pytest -q`: 942 passed, 100% measured statement/branch coverage.
- `uv run prek run --all-files`: passed; non-applicable hooks skipped.
- Changed Markdown was formatted directly with the installed Prettier binary because the repository hook skipped those file types.
- `uv run mkdocs build --strict --site-dir /tmp/python-bsblan-profile-docs`: passed.
- `git diff --check`: passed.
- Safety regressions cover adapter and controller-only changes while discovering another group, invalidation/cancellation races and fresh preflight on cached writes.
- No live-device access, HA integration edits, commits, pushes or merges. The standard profile registry remains empty; #1668 is an explicit diagnostic candidate only.
