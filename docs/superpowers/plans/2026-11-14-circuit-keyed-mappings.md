# Circuit-Keyed Schedule Mappings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace numbered heating configuration fields with one immutable
collection keyed by the circuit identifier already used by operations.

**Architecture:** `ScheduleMappings.heating` is a validated read-only mapping
from int to `ScheduleMapping`. Normalize canonical JSON keys, defensively freeze
it, and serialize it explicitly. The manager uses direct circuit lookup; the
flat read/write API, existing safeguards, and supported circuits stay unchanged.

**Tech Stack:** Existing Python/pydantic/pytest/aiohttp/uv/Ruff/prek only.

**Spec:** `docs/superpowers/specs/2026-11-14-circuit-keyed-mappings-design.md`

## Global Constraints

- Python 3.12+; no new dependencies.
- Response/configuration models use pydantic; update payloads remain dataclasses.
- Preserve `snake_case`, existing parameter names, and all schedule safety gates.
- Support circuit identifiers 1 and 2 only; do not infer new device capabilities.
- Keep the existing worktree/PR and original checkout untouched. No live device
  access, release, new parameter IDs, or unrelated implementation changes.
- Run full tests with 95%+ total/100% patch coverage and all `prek` hooks.

## Review Focus

- Empty default mapping must be immutable, not an unvalidated mutable default.
- JSON "1" plus Python 1 cannot silently collide after key normalization.
- True/1.0 and noncanonical string keys must not impersonate valid circuits.
- Mutating source dicts or serialized output must not retarget captured profiles.
- Missing circuit 2 must never fall back to circuit 1 for either operation.

## Execution

Native continuation was selected previously and the user approved updating this
PR. Use the existing isolated `refactor/unified-schedules` worktree. One task is
appropriate because the model, consumers, and fixtures form one API cutover.

---

### Task 1: Circuit-keyed model, lookup, and complete consumer migration

**Files:**

- Modify: `src/bsblan/schedules.py`, `src/bsblan/_schedules.py`,
  `examples/read_schedules.py`.
- Test/migrate: `tests/test_unified_schedule_models.py`,
  `tests/test_unified_schedules.py`, `tests/test_set_heating_schedule.py`,
  `tests/test_schedule_mapping_safety.py`, `tests/test_schedule_transport_safety.py`,
  `tests/test_jq_envelope_contract.py`, `tests/test_read_schedules_example.py`.
- Update: getting-started/migration/API docs and previous design/plan references.

**Interfaces:**

- Produces `ScheduleMappings(heating: Mapping[int, ScheduleMapping] = {},
hot_water: ScheduleMapping | None = None)` with immutable validated internals.
- Consumes `ScheduleMapping` unchanged; nested values retain strict ID validation.
- Preserves `heating_schedule(*, circuit: int = 1)` and
  `set_heating_schedule(update, *, circuit: int = 1)`.
- CLI continues accepting one optional heating profile and circuit selector;
  construct `heating={circuit: profile}` and iterate configured circuit keys.

- [ ] **Step 1: Add failing model tests.** Integer/canonical JSON keys normalize
      to identical profiles. Both empty and populated mappings reject mutation.
      Source dict/output changes do not affect the model. Normal deep copies and
      pydantic `model_copy(deep=True)` retain an immutable collection. Reject bool, float, 0/3,
      "01"/"1.0", duplicate 1/"1", non-mappings, None/invalid profiles, and old fields.
- [ ] **Step 2: Add failing HTTP routing tests.** Read and write circuits 1/2 with
      different literal IDs and confirm each selects its configured profile. With
      only circuit 1 configured, circuit 2 fails locally without requests or fallback.
- [ ] **Step 3: Run** `uv run pytest --no-cov -n 0 tests/test_unified_schedule_models.py
tests/test_set_heating_schedule.py`. Expected: RED for the missing keyed API.
- [ ] **Step 4: Implement the model/lookup.** Use a defensive read-only mapping,
      explicit serializer, default validation, and strict before-key validation.
      Use a frozen tuple-backed Mapping so normal configuration copying still works.
      Normalize accepted JSON keys only and detect duplicate canonical identifiers.
      Lookup heating profiles by circuit, not formatted strings or per-call profiles.
- [ ] **Step 5: Migrate CLI/tests/docs.** Preserve all original safeguards and
      failure/recovery cases. Update fixtures to numeric keys, not another named-field
      convention. Add coverage for CLI circuit 1/2 and exact JSON roundtrip output.
- [ ] **Step 6: Run** `uv run pytest --cov=src/bsblan --cov-report=term-missing -n 4`,
      `uv run prek run --all-files`, explicit Prettier, and strict MkDocs build.
      Expected: GREEN with all modified executable lines covered.
- [ ] **Step 7: Commit** `refactor: key heating schedule mappings by circuit`.
- [ ] **Step 8: Separate final self-review** (no subagent tool available): inspect
      model mutation/defaults, normalized-key collisions, serialization, routing and
      remaining old field references. Address important issues RED→GREEN.
- [ ] **Step 9: Push the existing PR branch and update its library-only description
      with the keyed configuration example and current test results.** Verify the
      remote head and text; do not merge or release.

## Plan self-review

The one task implements the model and all dependent consumers together. All five
Review Focus conditions have explicit tests in Steps 1/2, and no operation/API
change beyond the approved configuration shape is required.
