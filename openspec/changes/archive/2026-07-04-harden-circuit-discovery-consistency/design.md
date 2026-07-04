# Design: Harden Heating-Circuit Discovery Consistency

## Context

`get_available_circuits()` in [src/bsblan/bsblan.py](../../../src/bsblan/bsblan.py) short-circuits discovery with `self._json_api_version == MIN_SUPPORTED_JSON_API` — an exact string comparison against `"1.0"`. The basic single-circuit config (`API_BASIC`) is however selected by `VersionResolver.supports_full_config()` for the entire JSON-API range [1.0, 2.0), so a device reporting `"1.2"` bypasses the guard, probes circuit 2 via `CircuitConfig.PROBE_PARAMS`, and — because `API_BASIC` has an empty `heating_circuit2` section — a subsequent `state(circuit=2)` raises `BSBLANError` with `EMPTY_SECTION_PARAMS`.

Independently, the "active parameter value" predicate `value not in (None, "---")` exists in three places: `APIValidator._is_valid_param` (utility.py), the probe loop in `get_available_circuits`, and `_get_available_pps_circuits`. `CircuitConfig.INACTIVE_MARKER = "---"` was introduced as the intended single source of that marker but was never wired in (dead constant). This duplication caused trigger B of the original bug (discovery accepted values that validation rejected).

Constraints: no public API change, behavior-preserving except for the guard-range fix, coverage total ≥95% / patch 100%, `ty` type checking and Ruff via prek.

## Goals / Non-Goals

**Goals:**

- Basic-config devices (any JSON-API version in [1.0, 2.0)) never probe circuit 2; discovery returns `[1]` and sets `_available_circuits = {1}`.
- One shared predicate decides "param value is active" for validation and both discovery paths, sourced from `CircuitConfig.INACTIVE_MARKER`.

**Non-Goals:**

- `BSBLANCircuitNotAvailableError` (deferred; requires a paired home-assistant coordinator change).
- Any change to version resolution (`VersionResolver`), config selection, or the PPS discovery flow's semantics.
- Renaming/removing `MIN_SUPPORTED_JSON_API` (still used by `VersionResolver`).

## Decisions

### D1: Guard on `self._supports_full_config is False`, not version-string comparison

The capability flag is the exact signal that selects `API_BASIC` in `_copy_api_config`, so guarding on it makes discovery agree with the config by construction — no parallel version-range logic to keep in sync. Alternatives considered:

- *Parse and range-compare `_json_api_version`*: duplicates `VersionResolver` logic; drifts if thresholds change.
- *Check `self._api_data` section emptiness per circuit* (`if not self._api_data.get(section): continue`): also correct and more granular, but `_api_data` may be `None` when `get_available_circuits()` is called before `initialize()` (a supported config-flow pattern), whereas the flag check degrades gracefully — `None`/`True` fall through to probing, preserving current behavior exactly.

The `is False` identity check is deliberate: `_supports_full_config is None` (unresolved, e.g. discovery called standalone) must keep probing as today.

### D2: Module-level `is_param_value_active(param)` in utility.py

```python
def is_param_value_active(param: dict[str, Any] | None) -> bool:
    return bool(param) and param.get("value") not in (None, CircuitConfig.INACTIVE_MARKER)
```

- Placed in [src/bsblan/utility.py](../../../src/bsblan/utility.py) (module-level function, not a method) so both `APIValidator` and `BSBLAN` can import it without coupling the client to the validator class.
- Sources `"---"` from `CircuitConfig.INACTIVE_MARKER`, reviving the dead constant as single source of truth. utility.py already imports from constants (`ErrorMsg`), so no import-cycle risk.
- `APIValidator._is_valid_param` delegates to it (kept as a thin method — tests call it directly); both discovery loops in bsblan.py call the helper.
- Truthiness contract is preserved: empty dict / `None` param → inactive; `value` of `None` or `"---"` → inactive; everything else active. Pure refactor.

### D3: Test strategy

- New `test_get_available_circuits_basic_config_skips_discovery` in tests/test_circuit.py: sets `_supports_full_config = False` with `_json_api_version = "1.2"`, asserts `[1]`, `{1}`, and `_request` never awaited — this fails on current code (falls through the guard).
- Existing `test_get_available_circuits_json_api_v1_skips_discovery` updated to set `_supports_full_config = False` (as real initialization would for `"1.0"`), staying green.
- `tests/test_utility.py::test_is_valid_param` keeps passing via the delegating method; add direct coverage of `is_param_value_active` (including the `None`-param branch) to hold patch coverage at 100%.

## Risks / Trade-offs

- [Guard now depends on `_supports_full_config` being resolved] → When unresolved (`None`), probing proceeds as before; a basic-config device probed pre-initialize would still hit the old path. Acceptable: identical to current behavior for that call order, and `initialize()`-first is the documented flow.
- [Boolean-flag guard is coarser than per-section emptiness] → Fine today: `API_BASIC` is the only single-circuit config and the flag is its selector. If per-circuit configs ever diversify, revisit with section-emptiness checks.
- [Formatter/hook churn on edits (known repo gotcha)] → Batch edits atomically; run `SKIP=no-commit-to-branch uv run prek run --all-files` after.
