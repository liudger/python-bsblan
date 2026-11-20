# Automatic Decimal Schedule Profile Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically distinguish verified RVS21 integer and decimal weekday
layouts. Enable heating circuit 2 (HC2) when the selected variant's HC2 mapping is
compatible (for both integer and decimal variants).

**Architecture:** Add a decimal variant to `STANDARD_SCHEDULE_PROFILES`. Use the
existing identity and table checks to select a unique profile per schedule group,
without guessing IDs or relaxing API v3 compatibility checks.

**Tech Stack:** Python 3.12+, pydantic, pytest.

### Task 1: Add and test the decimal profile

**Files:** Modify `src/bsblan/schedule_profiles.py` and
`tests/test_standard_schedule_profiles.py`.

- [ ] **Write the regression tests first.** Assert exact weekday IDs and complete
      table signatures for both variants. With no manual mapping or table assertion,
      both integer and decimal layouts enable HC1, HC2 and domestic hot water (DHW)
      when compatible. An incompatible HC2 mapping stays disabled. Mock a conclusive
      `/JC` mismatch for the losing variant: missing rows are inconclusive and must
      not let another variant win.
- [ ] **Verify RED.** Run the command below and confirm that the new expectations
      fail without the decimal profile.

  ```bash
  uv run pytest --no-cov tests/test_standard_schedule_profiles.py
  ```

- [ ] **Add the profiles.** Use independently verified weekday IDs and exact
      installation scope. Ensure both integer and decimal variants contain HC1,
      HC2 and DHW mappings. Keep distinct profile IDs and `identity.table` values,
      preserve decimal IDs as strings, and declare a `table_parameters` entry for
      every mapped weekday. Retain existing fail-closed behavior for ambiguous or
      incomplete probes.
- [ ] **Verify GREEN.** Rerun the same command and confirm the module passes.

### Task 2: Run validation

- [ ] **Run the focused schedule tests.**

  ```bash
  uv run pytest --no-cov tests/test_standard_schedule_profiles.py \
    tests/test_schedule_profiles.py tests/test_schedule_profile_integration.py
  ```

- [ ] **Run the required repository checks.**

  ```bash
  uv run prek run --all-files
  ```
