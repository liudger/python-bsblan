# RVS21 integer and decimal schedule profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically support integer schedule IDs for HC1, HC2 and DHW, plus the issue-confirmed decimal IDs for HC1 and DHW on the exact reported installation.

**Architecture:** Add one narrowly scoped decimal `ScheduleProfile` alongside the existing integer profile. Keep the existing per-group resolver and strict identity/layout/value checks; profiles hold mappings per group so later groups can be added independently.

**Tech Stack:** Python 3.12+, Pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-rvs21-decimal-schedule-profile-design.md`

## Global Constraints

- Preserve exact profile identity matching and fail-closed behavior.
- Keep decimal IDs as canonical strings; never coerce them to floats.
- Only enable a profile after matching active `/JC` layout and compatible `/JQ` values.
- Do not add decimal HC2 IDs or scan parameter ranges.
- Keep line length <= 88 and all functions fully typed.

## Review Focus

- Integer-only profile regression: HC1, HC2, and DHW retain exact IDs.
- Decimal profile is limited to the exact reported firmware/BSB/destination/controller scope.
- Decimal DHW layout mismatch/incomplete response never enables the group.
- HC2 remains integer in both profiles; no decimal HC2 is inferred.
- Decimal IDs remain unchanged through reads and writes.

---

### Task 1: Add issue-backed profile regression tests and profile data

**Files:**
- Modify: `tests/test_standard_schedule_profiles.py`
- Modify: `src/bsblan/schedule_profiles.py`
- Modify: `tests/fixtures/rvs21_schedule_profile.json`

**Interfaces:** Existing `ScheduleProfile`, `ScheduleMappings`, and resolver APIs.

- [ ] Add failing tests for exact integer HC1/HC2/DHW mappings and exact-scope decimal HC1/DHW plus integer HC2 mappings.
- [ ] Add failing automatic discovery/read/write tests for the decimal DHW/HC1 IDs and integer HC2 IDs, using the French `/JC` weekday labels from issue #1668.
- [ ] Add/retain fail-closed tests for wrong firmware, wrong bus/destination, incompatible layout, and incomplete probe results.
- [ ] Run `uv run pytest --no-cov tests/test_standard_schedule_profiles.py` and verify the new expectations fail before implementation.
- [ ] Add the profile constants and a separate decimal `ScheduleProfile` scoped to `5.1.1-20260316232429`, BSB, destination 0, `RVS21.831F/127`, family 211, variant 127. Map HC1/DHW to decimal IDs and HC2 to integer IDs. Use exact French weekday signatures for this profile.
- [ ] Update the sanitized fixture with only profile provenance/IDs/labels/scope, not credentials or live program values.
- [ ] Rerun the focused test module and verify it passes.

### Task 2: Sync user-facing documentation and validate

**Files:**
- Modify: `docs/schedule-profiles.md`
- Modify: `docs/superpowers/plans/2026-11-20-auto-select-decimal-schedule-profile.md`

- [ ] Document both exact firmware scopes, supported IDs, group coverage, and the lack of decimal HC2 support.
- [ ] Run focused schedule tests:

  ```bash
  uv run pytest --no-cov tests/test_standard_schedule_profiles.py \
    tests/test_schedule_profiles.py tests/test_schedule_profile_integration.py \
    tests/test_set_heating_schedule.py tests/test_set_hot_water_schedule.py
  ```

- [ ] Run full tests: `uv run pytest --no-cov`.
- [ ] Run required checks: `uv run prek run --all-files`.
- [ ] Request a fresh Sol 6.2 review and update existing PR #1680 to close issue #1668 after review findings are resolved.
