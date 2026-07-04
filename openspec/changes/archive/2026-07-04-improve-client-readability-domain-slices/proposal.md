# Proposal: improve-client-readability-domain-slices

## Why

`src/bsblan/bsblan.py` is still ~1592 lines after the transport, version,
validation, and temperature extractions, and it mixes several remaining domain
concerns (hot water, schedules, low-level parameter reads, thermostat write
preparation). This makes the facade hard to scan and review, and the retry
policy still lacks characterization tests proving `401`/`403` responses are not
retried.

## What Changes

- Add missing retry characterization tests (`test_no_retry_on_401_auth_error`,
  `test_no_retry_on_403_auth_error`) before any refactoring, each registering a
  single mocked response and asserting `BSBLANAuthError`.
- Extract cohesive internal domain modules while keeping `BSBLAN` as the public
  facade with thin delegations:
  - `src/bsblan/_hot_water.py`: hot water getters/setters and hot water state
    preparation.
  - `src/bsblan/_schedules.py`: `heating_schedule`, `set_heating_schedule`, and
    `set_hot_water_schedule` shared schedule logic.
  - `src/bsblan/_parameters.py`: `read_parameters`, `get_parameter_id`,
    `get_parameter_ids`, and `read_parameters_by_name`.
  - Optionally `src/bsblan/_thermostat.py` for thermostat write preparation,
    only if it meaningfully reduces `BSBLAN` complexity without awkward
    callback wiring.
- Reuse existing helpers (`BSBLAN._request`, `_set_payload`,
  `_set_device_state`, `_apply_include_filter`, `_request_named_params`,
  `SectionValidator`, `TemperatureManager`) rather than duplicating logic.
- Update tests only where private implementation locations move.

No public `BSBLAN` method names, signatures, return types, exceptions,
constants, models, or documented user workflows change.

## Capabilities

### New Capabilities

- `client-retry-policy`: Characterizes the existing retry behavior for
  authentication failures — HTTP `401` and `403` responses raise
  `BSBLANAuthError` after a single request with no retries.

### Modified Capabilities

<!-- None. This is a behavior-preserving internal refactor; no existing
spec-level requirements change. -->

## Impact

- **Code**: `src/bsblan/bsblan.py` shrinks significantly; new internal modules
  `_hot_water.py`, `_schedules.py`, `_parameters.py` (and optionally
  `_thermostat.py`) are added. `constants.py` and `models.py` stay untouched
  unless strictly required by the extraction.
- **Tests**: `tests/test_backoff_retry.py` gains two tests; existing tests are
  updated only where they reference moved private implementation details.
  Coverage must stay ≥ 95% total with 100% patch coverage.
- **Docs**: No user-facing documentation changes expected (internal layout
  only).
- **Out of scope**: renaming `get_temperature_unit`, new user-facing APIs,
  parameter ID or cooling behavior changes, reorganizing `constants.py` /
  `models.py`, and any transport/retry/version/validation/temperature behavior
  changes beyond the two missing retry tests.
