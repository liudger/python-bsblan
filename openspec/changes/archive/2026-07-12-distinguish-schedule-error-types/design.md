## Context

`python-bsblan` currently exposes a single generic `BSBLANError` for a wide
range of failure modes. Two of them are semantically opposite from a retry
standpoint:

- **Unsupported schedule** — the device does not expose the requested
  time-program parameters. In `_schedules.heating_schedule()` this raises
  `BSBLANError(ErrorMsg.NO_HEATING_SCHEDULE_PARAMS)`, and in
  `_hot_water._get_filtered_data()` it raises `BSBLANError(error_msg)` for the
  hot-water schedule group. This is a **permanent** condition.
- **Malformed response** — the transport cannot decode or JSON-parse the body.
  In `_transport.request_with_retry()` this is caught from `ValueError` /
  `UnicodeDecodeError` and re-raised as
  `BSBLANError(ErrorMsg.INVALID_RESPONSE.format(e))`. This is a **transient**
  condition.

Because both surface as `BSBLANError`, a downstream integration (Home Assistant)
cannot decide whether to retry. It must either stop retrying (losing recovery
from transient malformed responses) or retry forever (uselessly hammering a
device that will never support a schedule after a write).

The library's own `backoff` decorator only retries `TimeoutError` and
`aiohttp.ClientError`, so `BSBLANError` is never retried inside the library; the
retry decision lives in the consumer. The fix is therefore an additive exception
taxonomy, not a change to the transport retry policy.

## Goals / Non-Goals

**Goals:**
- Let callers distinguish permanent unsupported-feature failures from transient
  malformed-response failures by `except` type.
- Keep the change fully backward compatible with existing `except BSBLANError`
  handlers.
- Reuse existing `ErrorMsg` strings; no message wording changes.

**Non-Goals:**
- Changing the transport-level `backoff` retry policy or which HTTP statuses are
  retried (`client-retry-policy` is unchanged).
- Adding automatic retry logic inside the library for schedules.
- Reclassifying other existing `BSBLANError` raise sites beyond schedule reads
  and malformed-response parsing.

## Decisions

**Decision: Two new subclasses of `BSBLANError`.**
Add `BSBLANUnsupportedFeatureError` (permanent) and
`BSBLANMalformedResponseError` (transient), both subclassing `BSBLANError`.
Subclassing preserves backward compatibility: any existing `except BSBLANError`
keeps catching them.
- *Alternative considered:* a single new error with a `retryable: bool`
  attribute. Rejected — attribute inspection is less idiomatic than `except`
  type matching and easier to get wrong at call sites.
- *Alternative considered:* schedule-specific name (e.g.
  `BSBLANUnsupportedScheduleError`). Chose the more general
  `BSBLANUnsupportedFeatureError` because the same permanent semantics apply to
  both heating and hot-water schedule reads and can extend to other
  unsupported-parameter cases later.

**Decision: Raise the permanent error at the schedule-read guard sites.**
Replace the bare `BSBLANError(...)` at
`_schedules.heating_schedule()` (no mapped data) and the hot-water schedule
branch in `_hot_water._get_filtered_data()` with
`BSBLANUnsupportedFeatureError`, keeping the existing `ErrorMsg` text. The
hot-water helper is shared by state/config/schedule reads, so scope the new
error to the schedule group only (via `group_name == "schedule"`) to avoid
reclassifying unrelated state/config failures.

**Decision: Raise the transient error at the transport parse site.**
In `_transport.request_with_retry()`, replace the
`raise BSBLANError(msg)` in the `(ValueError, UnicodeDecodeError)` handler with
`raise BSBLANMalformedResponseError(msg)`, reusing
`ErrorMsg.INVALID_RESPONSE`.

**Decision: Export the new exceptions from the package.**
Add both classes to `bsblan.exceptions` and to the package `__all__` /
re-exports so consumers can import them from the top-level `bsblan` namespace.

## Risks / Trade-offs

- **[Consumers catching the narrow generic message string]** → Mitigation:
  messages are unchanged; only the concrete type is narrower. Broad
  `except BSBLANError` still works.
- **[Over-scoping the hot-water helper]** → Mitigation: gate the new error on the
  schedule group so state/config reads keep raising the existing generic error
  and existing tests stay green.
- **[Missed raise site]** → Mitigation: grep for `NO_HEATING_SCHEDULE_PARAMS`,
  the hot-water schedule `error_msg`, and `INVALID_RESPONSE` to confirm all
  targeted sites are updated; add tests asserting the concrete types.

## Migration Plan

Additive, no migration required. Release as a minor version. Consumers may
optionally add narrower `except BSBLANUnsupportedFeatureError` /
`except BSBLANMalformedResponseError` handlers; existing code is unaffected.

## Open Questions

- Final class names: `BSBLANUnsupportedFeatureError` vs
  `BSBLANUnsupportedScheduleError`. Proposed the broader name; confirm during
  review.
