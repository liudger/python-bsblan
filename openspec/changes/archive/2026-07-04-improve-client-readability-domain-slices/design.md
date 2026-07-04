# Design: improve-client-readability-domain-slices

## Context

`src/bsblan/bsblan.py` is currently ~1592 lines. Previous behavior-preserving
stages already extracted:

- HTTP transport → `src/bsblan/_transport.py` (`BSBLANTransport`)
- version/capability resolution → `src/bsblan/_version.py` (`VersionResolver`)
- lazy API validation → `src/bsblan/_validation.py` (`SectionValidator`)
- temperature range/unit handling → `src/bsblan/_temperature.py`
  (`TemperatureManager`)

The remaining `BSBLAN` facade still mixes four large domain concerns:

1. Hot water: `hot_water_state`, `hot_water_config`, `hot_water_schedule`,
   `set_hot_water`, `_fetch_hot_water_data`, `_prepare_hot_water_state`
   (~L1074–1441).
2. Schedules: `heating_schedule`, `set_heating_schedule`,
   `set_hot_water_schedule` (~L1233–1402, overlapping hot water).
3. Low-level parameter reads: `read_parameters`, `get_parameter_id`,
   `get_parameter_ids`, `read_parameters_by_name` (~L1442–end).
4. Thermostat write preparation: `thermostat`, `_prepare_thermostat_state`,
   `_thermostat_params`, HVAC/cooling-mode validation (~L836–1030).

Constraints:

- Behavior-preserving: no public API, exception, model, or constant changes.
- The `mock_bsblan` fixture and many tests monkeypatch `bsblan._request` (and
  other private attributes) **after** construction, so collaborators must read
  facade state via live lambdas, not captured bound methods (proven pattern
  from the `SectionValidator` / `TemperatureManager` extractions).
- Coverage gate: ≥95% total, 100% patch coverage.
- A PostToolUse hook runs full validation after Python edits; multi-file edits
  should be batched atomically so the Ruff autofix hook never sees a broken
  intermediate state (it strips transiently-unused imports).

## Goals / Non-Goals

**Goals:**

- Add the two missing retry characterization tests (401/403 → single request,
  `BSBLANAuthError`, no retry) *before* refactoring.
- Extract hot water, schedule, and parameter-read logic into focused internal
  modules; keep `BSBLAN` as a thin public facade.
- Make `bsblan.py` visibly smaller and easier to scan.
- Keep every existing test green with edits limited to moved private
  implementation locations.

**Non-Goals:**

- Renaming `get_temperature_unit` or adding user-facing APIs.
- Changing parameter IDs, cooling behavior, or retry/transport/version/
  validation/temperature behavior.
- Reorganizing `constants.py` or `models.py`.
- User-facing documentation changes.

## Decisions

### D1: Retry tests first, in `tests/test_backoff_retry.py`

Add `test_no_retry_on_401_auth_error` and `test_no_retry_on_403_auth_error`
before any extraction. Each registers exactly one mocked response and asserts
`BSBLANAuthError`. Registering a single response inherently proves no retry
occurred (a retry would find no registered response and fail differently).
This pins the auth/no-retry contract so the refactor cannot silently regress
it. No transport code changes.

### D2: Collaborator classes with live-lambda wiring (same pattern as Stages 4–5)

Each extracted module holds a small class constructed in
`BSBLAN.__post_init__` with keyword-only callbacks:

- `src/bsblan/_hot_water.py` — `HotWaterManager`: owns
  `_fetch_hot_water_data`, `_prepare_hot_water_state`, and the bodies of
  `hot_water_state`, `hot_water_config`, `hot_water_schedule`,
  `set_hot_water`.
- `src/bsblan/_schedules.py` — `ScheduleManager`: owns the bodies of
  `heating_schedule`, `set_heating_schedule`, `set_hot_water_schedule`, and
  the shared schedule parse/serialize logic. Note: `heating_schedule`
  intentionally keeps its own by-key mapping (tolerates missing params) and is
  NOT routed through `_request_named_params`.
- `src/bsblan/_parameters.py` — `ParameterReader`: owns the bodies of
  `read_parameters`, `get_parameter_id`, `get_parameter_ids`,
  `read_parameters_by_name`.

Callbacks that tests monkeypatch on the facade (`_request`, `_set_payload`
usage sites, `static_values`, etc.) are passed as live lambdas
(`lambda **kw: self._request(**kw)  # noqa: PLW0108`); stable helpers may be
passed as bound methods only if verified un-monkeypatched (grep both attribute
and string forms, e.g. `"_prepare_hot_water_state"`).

Alternative considered: plain module-level functions taking the client as
first argument. Rejected: collaborator classes match the established
`_transport`/`_validation`/`_temperature` pattern and keep the callback
surface explicit and testable.

### D3: Facade keeps thin delegations with unchanged signatures/docstrings

Every public method (`hot_water_state`, `set_hot_water`, `heating_schedule`,
`read_parameters`, …) stays on `BSBLAN` and delegates in one or two lines.
Private helpers that tests call directly (check via grep before deleting —
e.g. `_prepare_hot_water_state`, `_fetch_hot_water_data`) either keep a thin
delegation on the facade or the tests are redirected to the collaborator,
whichever is the smaller diff. State that is shared across domains
(`_api_data`, `_available_circuits`) stays on the facade.

### D4: Thermostat extraction is conditional (evaluate last)

`_prepare_thermostat_state` depends on `TemperatureManager` validation,
`_validate_hvac_mode`, `_validate_cooling_operating_mode`, PPS guards, and
`_thermostat_params`. Extract to `src/bsblan/_thermostat.py` only if the
result removes more complexity from `bsblan.py` than the callback wiring adds
(rough test: net line reduction in `bsblan.py` and ≤6 constructor callbacks).
Otherwise leave it on the facade and record the decision in tasks.

### D5: One extraction per commit, atomic multi-file edits

Each module extraction lands as its own commit with tests green, mirroring the
earlier stage-per-PR discipline. Edits that add imports plus their consumers
are applied in one batch so the Ruff autofix hook cannot strip
transiently-unused imports.

## Risks / Trade-offs

- [Tests monkeypatch moved privates by string name, missed by attribute grep]
  → Grep both `\._name` and `"_name"` string forms across `tests/` before
  moving each method (this bit Stage 4 twice).
- [Ruff autofix strips imports between edit batches] → Batch each extraction
  atomically; put annotation-only imports in `TYPE_CHECKING` blocks in the
  same edit that introduces their first usage.
- [Callback wiring grows facade `__post_init__`] → Acceptable: `__post_init__`
  becomes the single explicit wiring map; each collaborator gets only the
  callbacks it needs.
- [Coverage drops if delegations are untested] → Delegations are one-liners
  exercised by existing public-behavior tests; run
  `uv run pytest --cov=src/bsblan --cov-report=term-missing` after each
  extraction.
- [Thermostat extraction makes wiring awkward] → D4 makes it explicitly
  optional; skipping it is an acceptable outcome.

## Migration Plan

Internal-only refactor; no deployment or user migration. Rollback = revert the
extraction commit(s). Suggested order (each step independently green):

1. Retry characterization tests.
2. `_parameters.py` (smallest, fewest callbacks).
3. `_hot_water.py`.
4. `_schedules.py` (depends on hot-water fetch helpers staying reachable).
5. Optional `_thermostat.py` evaluation.

## Open Questions

- Whether `_thermostat.py` clears the D4 bar — decided during implementation,
  not blocking.
- Whether `set_hot_water_schedule` lives in `_hot_water.py` or
  `_schedules.py`: default is `_schedules.py` (shared schedule
  serialization), but if it shares more code with `set_hot_water` payload
  preparation, keep schedule serialization helpers in `_schedules.py` and let
  `HotWaterManager` call them.
