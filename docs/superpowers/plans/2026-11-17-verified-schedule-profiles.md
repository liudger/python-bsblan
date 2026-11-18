# Verified Schedule Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe, read-only automatic schedule resolution for evidence-backed profiles.

**Architecture:** Immutable profile/availability models describe exact identities and provenance. A separate resolver matches fresh device/controller metadata and probes candidate IDs; the existing schedule manager consumes it without changing manual overrides.

**Tech Stack:** Python 3.12+, pydantic, aiohttp, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-11-17-verified-schedule-profiles-design.md`

## Global Constraints

- Python 3.12+, API v3 baseline; no new dependencies or HA Core changes.
- Preserve immutable circuit-keyed mappings, PPS rejection, sequential `/JS` writes, clear rejection, partial-write reporting and manual target guards.
- No built-in guessed profile, writable probe, firmware-only selection, background retry loop, schedule persistence or automatic destructive clearing.
- A new client is required after changing the asserted active table or profiles.

## Review Focus

- Overlapping profiles must never select a group by registry order.
- Transient failures must not produce permanent mapping repairs or negative caches.
- Target or cached bus metadata changes during an await must block writes.
- Unknown interval formats with correct TIMEPROG metadata are compatible mappings.
- Manual-only clients and normal startup must retain existing request behavior.

### Task 1: Profile models and compatibility resolver

**Files:** Create `src/bsblan/schedule_profiles.py`, `src/bsblan/_schedule_profiles.py`, `tests/test_schedule_profiles.py`.

**Interfaces:** Public `ScheduleProfileIdentity`, `ScheduleProfile`, `ScheduleAvailability`; empty `STANDARD_SCHEDULE_PROFILES`. Internal `ScheduleProfileResolver.resolve(kind, circuit)` returns availability, mapping and raw probe data. Constructor takes request/device callbacks, profiles and asserted table ID.

- [x] Write failing tests for immutable models, required evidence, empty defaults, exact matching, missing identity/table evidence, ambiguity and independently supported groups.
- [x] Run `uv run pytest --no-cov tests/test_schedule_profiles.py` and confirm missing functionality.
- [x] Implement models and resolver with strict identity matching and no ID scanning.
- [x] Add failing probe tests: all seven IDs, wrong/bool/string types, inactive/missing data, transient errors, error 7, malformed responses, unsupported interval text and connection failure recovery.
- [x] Implement conservative compatibility classification; preserve network/auth/malformed exceptions.
- [x] Run focused tests; verify all pass.

### Task 2: Integrate discovery and automatic schedule operations

**Files:** Modify `src/bsblan/bsblan.py`, `src/bsblan/_schedules.py`, `src/bsblan/exceptions.py`, `src/bsblan/__init__.py`; extend profile tests.

**Interfaces:** `BSBLANConfig.schedule_profiles`, `BSBLANConfig.schedule_table`; `BSBLAN.discover_schedules() -> tuple[ScheduleAvailability, ...]`; `BSBLANScheduleProbeError`. Existing readers/setters unchanged externally.

- [x] Write failing integration tests for manual precedence, discovery statuses, automatic reads reusing probe data, automatic writes probing first and per-group enablement.
- [x] Run tests to confirm failures, then wire resolver into existing manager.
- [x] Add failing safety tests for invalid circuits, PPS, target changes during identity/probe/write, retries without repairs, and unchanged manual/startup requests.
- [x] Implement target/metadata guards and distinct probe errors without caching automatic mappings.
- [x] Run `uv run pytest`; fix regressions without weakening manual safety checks.

### Task 3: Documentation and final verification

**Files:** Modify `README.md`, `docs/getting-started.md`, `docs/schedule-migration.md`, `docs/api/client.md`; add profile evidence/consumer guidance.

**Interfaces:** Document statuses, repair/retry handling, table identity limitation and explicit overrides using public names from Tasks 1/2.

- [x] Document that no built-in profile is certified yet; explain evidence needed to add one and how verified deployments can supply profiles.
- [x] Review the complete diff against the design; add missing tests.
- [x] Run full coverage; cover every changed executable line and retain >=95% total.
- [x] Run `uv run prek run --all-files`, resolve findings, and rerun until clean.
- [x] Record verification results and remaining evidence limitation; leave changes on the requested branch without pushing or merging.

## Verification results

- `uv run pytest -q`: 883 passed; 100% measured statement/branch coverage.
- `uv run prek run --all-files`: passed (non-applicable hooks skipped).
- Prettier was also run directly on changed Markdown/YAML because the repository hook skipped those file types.
- `uv run mkdocs build --strict --site-dir /tmp/python-bsblan-profile-docs`: passed.
- `git diff --check`: passed.
- No live device writes or reads were performed; profile tests and HTTP fixtures are synthetic.
- Remaining prerequisite for zero-setup defaults: independently verified active-table identity and the first reviewed real-controller profile. Built-in registry intentionally stays empty.
- Changes remain uncommitted on `feat/verified-schedule-profiles`; nothing pushed or merged.
