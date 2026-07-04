# Tasks: improve-client-readability-domain-slices

## 1. Retry Characterization Tests

- [x] 1.1 Add `test_no_retry_on_401_auth_error` to `tests/test_backoff_retry.py`
      registering exactly one mocked `401` response and asserting
      `BSBLANAuthError`
- [x] 1.2 Add `test_no_retry_on_403_auth_error` with one mocked `403` response
      asserting `BSBLANAuthError`
- [x] 1.3 Run `uv run pytest --no-cov tests/test_backoff_retry.py` and confirm
      green

## 2. Extract Parameter Reads (`_parameters.py`)

- [x] 2.1 Grep `tests/` for attribute AND string-form references to
      `read_parameters`, `get_parameter_id`, `get_parameter_ids`,
      `read_parameters_by_name` and any private helpers they use
- [x] 2.2 Create `src/bsblan/_parameters.py` with a `ParameterReader` class
      owning the method bodies; wire monkeypatched callbacks (`_request`, …)
      as live lambdas in `BSBLAN.__post_init__`
- [x] 2.3 Reduce the four `BSBLAN` methods to thin delegations with unchanged
      signatures, docstrings, return types, and exceptions
- [x] 2.4 Redirect any tests that reference moved privates; run full
      `uv run pytest --cov=src/bsblan --cov-report=term-missing` and confirm
      coverage gate

## 3. Extract Hot Water (`_hot_water.py`)

- [x] 3.1 Grep `tests/` for references to `_fetch_hot_water_data`,
      `_prepare_hot_water_state`, `hot_water_*`, `set_hot_water` privates
      (attribute and string forms)
- [x] 3.2 Create `src/bsblan/_hot_water.py` with `HotWaterManager` owning
      `_fetch_hot_water_data`, `_prepare_hot_water_state`, and the bodies of
      `hot_water_state`, `hot_water_config`, `hot_water_schedule`,
      `set_hot_water`; reuse `SectionValidator` hot-water cache/group APIs and
      facade helpers (`_apply_include_filter`, `_set_payload`,
      `_set_device_state`) via callbacks
- [x] 3.3 Keep `BSBLAN` hot-water methods as thin delegations; keep
      `set_hot_water_cache` public delegation unchanged
- [x] 3.4 Redirect moved-private test references; run full coverage suite and
      confirm green

## 4. Extract Schedules (`_schedules.py`)

- [x] 4.1 Grep `tests/` for references to `heating_schedule`,
      `set_heating_schedule`, `set_hot_water_schedule` internals
- [x] 4.2 Create `src/bsblan/_schedules.py` with `ScheduleManager` owning
      shared schedule parse/serialize logic plus the bodies of
      `heating_schedule`, `set_heating_schedule`, `set_hot_water_schedule`;
      preserve `heating_schedule`'s tolerant by-key mapping (do NOT route
      through `_request_named_params`)
- [x] 4.3 Keep facade methods as thin delegations; decide `_hot_water.py` vs
      `_schedules.py` placement for DHW schedule serialization per design D5
      open question and record the choice here
      → Decision: DHW schedule writes live in `_schedules.py`
      (`ScheduleManager._write_day_schedules` is shared by heating and DHW);
      `set_hot_water` payload prep stays in `_hot_water.py` (no overlap).
- [x] 4.4 Redirect moved-private test references; run full coverage suite and
      confirm green (459 passed, 100% coverage; no test edits needed)

## 5. Evaluate Optional Thermostat Extraction (`_thermostat.py`)

- [x] 5.1 Assess per design D4: extract `_prepare_thermostat_state`,
      `_thermostat_params`, and HVAC/cooling-mode validation only if it nets a
      line reduction in `bsblan.py` with ≤6 constructor callbacks
      → Extracted: `ThermostatWriter` needs only 3 callbacks
      (`uses_pps_bus`, `temperature`, `set_payload`) and removes ~120 lines.
- [x] 5.2 If extracting: create `src/bsblan/_thermostat.py`, keep
      `thermostat()` as facade delegation, redirect tests, run coverage suite.
      If skipping: record the rationale in this file and mark done
      → Done. `thermostat()` stays public on the facade;
      `_validate_target_temperature[_high]` delegations kept (test-referenced);
      no test edits needed. 459 passed, 100% coverage.

## 6. Final Validation

- [x] 6.1 Verify no public API changes: `BSBLAN` method names, signatures,
      return types, and exceptions unchanged; no edits to `constants.py` /
      `models.py` unless strictly required (document any)
      → Verified: refactor diff touches only new `_*.py` modules, `bsblan.py`
      (1592 → 1295 lines), and `tests/test_backoff_retry.py`.
- [x] 6.2 Confirm no user-facing docs changes are needed (README, docs/)
      → No internal references in docs; no behavior changes.
- [x] 6.3 Run `uv run pytest --no-cov tests/test_backoff_retry.py`
      → 12 passed.
- [x] 6.4 Run `uv run pytest --cov=src/bsblan --cov-report=term-missing`;
      confirm total ≥95% and 100% patch coverage on modified lines
      → 459 passed, 100.00% total coverage (0 missing lines).
- [x] 6.5 Run `SKIP=no-commit-to-branch uv run prek run --all-files` and
      resolve any formatter/lint churn (expect one autofix pass)
      → All hooks green.
