# Tasks: Harden Heating-Circuit Discovery Consistency

## 1. Shared active-value predicate (pure refactor)

- [x] 1.1 Add module-level `is_param_value_active(param: dict[str, Any] | None) -> bool` to `src/bsblan/utility.py`, sourcing the inactive marker from `CircuitConfig.INACTIVE_MARKER` (import from `.constants`); semantics: non-empty payload AND `value` not in `(None, INACTIVE_MARKER)`
- [x] 1.2 Delegate `APIValidator._is_valid_param` to `is_param_value_active` (keep the method — tests call it directly)
- [x] 1.3 In `src/bsblan/bsblan.py` `get_available_circuits()` probe loop, replace `if not param_data or param_data.get("value") in (None, "---"):` with `if not is_param_value_active(param_data):` (import helper from `.utility`)
- [x] 1.4 In `_get_available_pps_circuits()`, replace the two-step empty-dict + `value in (None, "---")` checks with a single `is_param_value_active` check (preserve the debug-log behavior for the reject path)

## 2. Basic-config discovery guard

- [x] 2.1 In `get_available_circuits()`, replace `if self._json_api_version == MIN_SUPPORTED_JSON_API:` with `if self._supports_full_config is False:` (keep returning `[1]` and setting `self._available_circuits = {1}`); update the debug log message to reference basic configuration instead of "JSON-API version 1.0"
- [x] 2.2 Remove the now-unused `MIN_SUPPORTED_JSON_API` import from `bsblan.py` if no other usage remains (it stays in `_version.py`/`constants.py`)

## 3. Tests

- [x] 3.1 Add `test_get_available_circuits_basic_config_skips_discovery` in `tests/test_circuit.py`: set `_supports_full_config = False` and `_json_api_version = "1.2"`, assert return `[1]`, `_available_circuits == {1}`, and `_request` not awaited (note: `mock_bsblan_circuit` fixture sets `_supports_full_config = True`, so override after fixture)
- [x] 3.2 Update existing `test_get_available_circuits_json_api_v1_skips_discovery` to set `_supports_full_config = False` (mirrors real resolution for "1.0"); keep its assertions green
- [x] 3.3 Verify full-config and unresolved-capability paths still probe: confirm existing probe tests pass with `_supports_full_config = True` from the fixture; add a `None`-capability probe test only if not already covered
- [x] 3.4 In `tests/test_utility.py`, keep `test_is_valid_param` green via delegation and add direct tests for `is_param_value_active` (active value, `"---"`, `None` value, empty dict, `None` payload) for 100% patch coverage

## 4. Validation

- [x] 4.1 Run `uv run pytest --no-cov tests/test_circuit.py tests/test_utility.py`
- [x] 4.2 Run `SKIP=no-commit-to-branch uv run prek run --all-files` and confirm green (expect one possible formatter pass)
- [x] 4.3 Confirm coverage gates: total ≥95%, patch 100% (`uv run pytest --cov=src/bsblan --cov-report=term-missing`)
