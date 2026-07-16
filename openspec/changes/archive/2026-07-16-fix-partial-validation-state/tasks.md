## 1. Parameter-Level Validation Coverage

- [x] 1.1 Replace coarse section completion tracking in `APIValidator` with
  per-section parameter-ID coverage, including reset behavior.
- [x] 1.2 Update lazy section validation to derive the current requested IDs,
  gate on their coverage, and retain unsupported-ID removal behavior.
- [x] 1.3 Replace coarse hot-water group completion tracking with per-group
  parameter-ID coverage and keep the cache synchronized with validated IDs.
- [x] 1.4 Ensure empty include-filter results add no coverage and do not mark a
  section or hot-water group complete.

## 2. Regression Coverage

- [x] 2.1 Add section tests for filtered-then-unfiltered and
  differently-filtered reads, asserting uncovered IDs are validated once.
- [x] 2.2 Add a section test showing a later-discovered unsupported ID is
  removed before the complete read is mapped.
- [x] 2.3 Update hot-water include tests to assert a partial request does not
  complete the group, then add filtered-then-unfiltered and
  differently-filtered regression cases.
- [x] 2.4 Update the empty include-filter test to assert no completion state is
  recorded and a later valid request performs validation.
- [x] 2.5 Retain or extend locking coverage to prove sequentially serialized
  requests recheck their own parameter coverage.

## 3. Validation

- [x] 3.1 Run focused validation and include-filter tests with `--no-cov`.
- [x] 3.2 Run `uv run prek run --all-files` and resolve all reported failures.
