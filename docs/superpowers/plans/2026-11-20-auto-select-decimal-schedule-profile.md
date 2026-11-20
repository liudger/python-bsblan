# Automatic Decimal Schedule Profile Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep default automatic schedule support strictly within independently
verified scope; only add integer/decimal/HC2 groups to `STANDARD_SCHEDULE_PROFILES`
when group-level evidence and a conclusive layout discriminator are documented.

**Architecture:** Start with a read-only evidence gate. If evidence proves a safe,
conclusive discriminator for overlapping variants, implement profile additions with
existing fail-closed resolver behavior. If evidence is incomplete/inconclusive,
preserve current narrow defaults and keep broader mappings explicit/diagnostic.

**Tech Stack:** Python 3.12+, pydantic, pytest.

### Task 1: Evidence gate (read-only, mandatory before code changes)

**Files:**
- Modify: `docs/schedule-profiles.md`
- Modify: `tests/fixtures/rvs21_schedule_profile.json` (only if new sanitized evidence exists)
- Modify: `docs/superpowers/plans/2026-11-20-auto-select-decimal-schedule-profile.md`

- [ ] **Record per-group evidence.** For each candidate group (integer HC2,
      decimal HC1/HC2/DHW), document exact installation scope and independent
      weekday-role evidence. If evidence is missing for a group, mark that group
      out-of-scope for default registry updates.
- [ ] **Record discriminator evidence.** Capture/document sanitized read-only `/JC`
      responses for both candidate requests in overlapping scopes. Confirm the
      losing variant is rejected conclusively (not merely incomplete/omitted).
- [ ] **Decision gate.**
  - If all required evidence is conclusive: proceed to Task 2.
  - If any required evidence is missing/inconclusive: skip Task 2 profile expansion
    and keep current default support unchanged.

### Task 2: Conditional profile implementation (only after Task 1 passes)

**Files (if gate passes):**
- Modify: `src/bsblan/schedule_profiles.py`
- Modify: `tests/test_standard_schedule_profiles.py`
- Modify: `tests/test_copilot_schedule_safety.py` and/or `tests/test_device_destination_validation.py` as needed

- [ ] **Write regression tests first (RED).** Assert only evidence-backed groups
      are default-enabled. Include regression for overlap handling where an omitted
      losing-layout `/JC` result stays inconclusive and must not silently select a
      winner.
- [ ] **Run RED check.**

  ```bash
  uv run pytest --no-cov tests/test_standard_schedule_profiles.py
  ```

- [ ] **Implement minimal profile changes.** Add/update only evidence-backed
      mappings with distinct `identity.table` values and complete signatures.
      Preserve fail-closed behavior for ambiguous/incomplete probes.
- [ ] **Run GREEN check.** Re-run the same module until passing.

### Task 3: Validation and documentation sync

- [ ] **Run focused schedule tests.**

  ```bash
  uv run pytest --no-cov tests/test_standard_schedule_profiles.py \
    tests/test_schedule_profiles.py tests/test_schedule_profile_integration.py \
    tests/test_copilot_schedule_safety.py tests/test_device_destination_validation.py
  ```

- [ ] **Run full test suite.**

  ```bash
  uv run pytest --no-cov
  ```

- [ ] **Run required repository checks.**

  ```bash
  uv run prek run --all-files
  ```

- [ ] **Sync supported-scope docs.** Ensure `docs/schedule-profiles.md` and any
      evidence fixture text exactly match what is default-enabled in code.
