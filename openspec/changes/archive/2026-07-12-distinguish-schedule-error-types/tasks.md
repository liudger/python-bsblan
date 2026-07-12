## 1. Exceptions

- [x] 1.1 Add `BSBLANUnsupportedFeatureError(BSBLANError)` to `src/bsblan/exceptions.py` with a docstring describing it as a permanent (non-retryable) condition.
- [x] 1.2 Add `BSBLANMalformedResponseError(BSBLANError)` to `src/bsblan/exceptions.py` with a docstring describing it as a transient (retryable) condition.
- [x] 1.3 Import and re-export both new exceptions in `src/bsblan/__init__.py` and add them to `__all__`.

## 2. Schedule read paths (permanent error)

- [x] 2.1 In `src/bsblan/_schedules.py` `heating_schedule()`, raise `BSBLANUnsupportedFeatureError(ErrorMsg.NO_HEATING_SCHEDULE_PARAMS)` when no schedule parameters are mapped (replace the bare `BSBLANError`).
- [x] 2.2 In `src/bsblan/_hot_water.py` `fetch_data()`, raise `BSBLANUnsupportedFeatureError(error_msg)` when the schedule group (`group_name == "schedule"`) has no filtered params, keeping other groups on the existing generic error.
- [x] 2.3 Update the `Raises:` docstrings on the affected schedule methods to reference the new exception type.

## 3. Transport parse path (transient error)

- [x] 3.1 In `src/bsblan/_transport.py` `request_with_retry()`, raise `BSBLANMalformedResponseError(msg)` from the `(ValueError, UnicodeDecodeError)` handler (replace the bare `BSBLANError`), reusing `ErrorMsg.INVALID_RESPONSE`.
- [x] 3.2 Update the `Raises:` docstring on `request_with_retry()` to reference the new exception type.

## 4. Tests

- [x] 4.1 Add a test asserting `heating_schedule()` raises `BSBLANUnsupportedFeatureError` when schedule params are absent, and that it is also a `BSBLANError`.
- [x] 4.2 Add a test asserting hot-water `schedule()` raises `BSBLANUnsupportedFeatureError` when schedule params are absent.
- [x] 4.3 Add a test asserting a non-JSON / undecodable response raises `BSBLANMalformedResponseError` and that it is also a `BSBLANError`.
- [x] 4.4 Verify existing state/config hot-water tests still raise the generic `BSBLANError` (no regression from the group gating).

## 5. Documentation & validation

- [x] 5.1 Document the two new exceptions in `docs/api/exceptions.md`.
- [x] 5.2 Run `uv run prek run --all-files` and `uv run pytest --cov=src/bsblan --cov-report=term-missing`; ensure total coverage stays >= 95% and patch coverage is 100%.
