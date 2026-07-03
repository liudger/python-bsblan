## 1. Device Verification

- [x] 1.1 Query raw data for params `901` and `1201` with `examples/fetch_param.py` on the real device; record `data_type`, value, unit, and `possibleValues`
- [x] 1.2 Finalize the valid value set and model type (`EntityInfo[int]` vs `EntityInfo[str]`) from the evidence; update design.md Open Questions

## 2. Constants

- [x] 2.1 Add `"901": "cooling_operating_mode"` to `BASE_HEATING_PARAMS` and `"1201": "cooling_operating_mode"` to `BASE_HEATING_CIRCUIT2_PARAMS` in src/bsblan/constants.py
- [x] 2.2 Add `"cooling_operating_mode": "901"` / `"1201"` to `CircuitConfig.THERMOSTAT_PARAMS` circuits 1 and 2
- [x] 2.3 Add `Validation.COOLING_OPERATING_MODES` with the device-confirmed value set

## 3. Model

- [x] 3.1 Add optional `cooling_operating_mode` field to `State` in src/bsblan/models.py (type per task 1.2)

## 4. Client Setter

- [x] 4.1 Add `cooling_operating_mode: int | None = None` to `thermostat()` and its internal set helper in src/bsblan/bsblan.py, sending one `/JS` request via `_set_payload` when populated
- [x] 4.2 Add `_validate_cooling_operating_mode` (mirror `_validate_hvac_mode`) raising `BSBLANInvalidParameterError` for out-of-set values
- [x] 4.3 Raise `BSBLANInvalidParameterError` when `cooling_operating_mode` is passed on a PPS-bus device (no cooling entry in PPS thermostat params)

## 5. Tests

- [x] 5.1 Extend state fixtures/tests: circuit 1 and circuit 2 reads populate `cooling_operating_mode`; absent/`"---"` param yields `None` without error
- [x] 5.2 Add setter tests: single `/JS` payload for circuit 1 and 2, multi-parameter call rejected (single-parameter contract), invalid value rejected before any request
- [x] 5.3 Add PPS rejection test
- [x] 5.4 Verify basic-config path does not request `901` (existing basic-config test coverage extended if needed)

## 6. Docs & Validation

- [x] 6.1 Update README and docs (getting-started/index/models) feature listing per feature-doc-updates convention
- [x] 6.2 Run `uv run pytest --cov=src/bsblan --cov-report=term-missing` (total ≥ 95%, patch 100%)
- [x] 6.3 Run `SKIP=no-commit-to-branch uv run prek run --all-files` until green
