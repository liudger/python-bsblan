# Harden Heating-Circuit Discovery Consistency

## Why

The circuit-discovery fix (plans/circuit-discovery-fix-plan.md, #1527/#1533) left two residual gaps. First, `get_available_circuits()` skips circuit probing only when the reported JSON-API version is exactly `"1.0"`, but the basic single-circuit config is selected for the whole range [1.0, 2.0) — a device reporting e.g. `"1.2"` still probes circuit 2 and can crash `state(circuit=2)` with `EMPTY_SECTION_PARAMS`. Second, the "parameter value is active" rule (`value not in (None, "---")`) is duplicated in three places while the intended constant `CircuitConfig.INACTIVE_MARKER` remains dead code, inviting future drift like trigger B of the original bug.

## What Changes

- Replace the exact-string guard `self._json_api_version == MIN_SUPPORTED_JSON_API` in `get_available_circuits()` with the capability signal that actually selects the basic config: `self._supports_full_config is False`. Behavior when `_supports_full_config` is `None` or `True` is unchanged; the basic-config path still returns `[1]` and sets `_available_circuits = {1}`.
- Extract a single helper `is_param_value_active(param)` in `src/bsblan/utility.py`, sourcing the inactive marker from `CircuitConfig.INACTIVE_MARKER`, and reuse it at all three duplication sites: `APIValidator._is_valid_param`, `get_available_circuits`, and `_get_available_pps_circuits`. Pure refactor, no behavior change.
- Add `test_get_available_circuits_basic_config_skips_discovery` covering a JSON-API version like `"1.2"` (currently falls through the guard); keep the existing `"1.0"` test green; adjust tests touching `_is_valid_param` internals as needed.

Out of scope: `BSBLANCircuitNotAvailableError` (deferred; requires a paired home-assistant bsblan coordinator change).

## Capabilities

### New Capabilities

- `circuit-discovery`: Heating-circuit discovery behavior — basic-config short-circuit driven by the resolved capability flag, probe-based discovery for full config, PPS single-circuit detection, and a single shared active-value predicate.

### Modified Capabilities

<!-- none — existing specs (client-retry-policy, cooling-operating-mode) are unaffected -->

## Impact

- `src/bsblan/bsblan.py`: `get_available_circuits()` guard condition; both discovery loops use the shared predicate.
- `src/bsblan/utility.py`: new `is_param_value_active()` helper; `APIValidator._is_valid_param` delegates to it.
- `src/bsblan/constants.py`: `CircuitConfig.INACTIVE_MARKER` becomes the single source of the `"---"` marker (no value change).
- `tests/test_circuit.py`, `tests/test_utility.py`: new basic-config discovery test; existing `"1.0"` test updated to set the capability flag it now depends on.
- No public API change; coverage gates unchanged (total ≥95%, patch 100%).
