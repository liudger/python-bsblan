## Why

Lazy validation currently records a section or hot-water group as fully
validated after a request filtered with `include`. This can leave unsupported
parameters in a section or leave the hot-water cache incomplete, causing later
unfiltered reads to skip necessary validation and return incomplete data or fail
while mapping a device response.

## What Changes

- Track validation coverage at the parameter level for sections and hot-water
  groups instead of treating any successful filtered request as complete.
- Ensure a later request validates parameter names that an earlier `include`
  request did not cover.
- Keep validation completion correct when an include filter has no matching
  parameters.
- Add focused regression coverage for filtered-then-unfiltered and
  differently-filtered reads.

## Capabilities

### New Capabilities

- `lazy-validation-completeness`: Lazy section and hot-water validation covers
  every parameter required by each request before that request uses the cached
  configuration.

### Modified Capabilities

- None.

## Impact

- Affected code: `src/bsblan/_validation.py`, `src/bsblan/utility.py`, and the
  lazy section and hot-water read paths that use their validation state.
- Affected tests: validation, include-filter, and hot-water regression tests.
- Public API: no signature changes; `include` calls may perform an additional
  validation request when they need parameters not checked by a prior call.
