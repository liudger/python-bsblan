## Context

`SectionValidator` lazily validates device parameter support before a section or
hot-water group is read. It currently stores completion as a section-wide set in
`APIValidator` and a group-wide set in `SectionValidator`. An `include` request
validates only a subset but records that coarse completion state, so a later
request for different names or all names can skip validation.

The resulting configuration has not established whether every requested
parameter is supported. For normal sections, an unvalidated parameter can remain
in the configuration and later produce a strict response-mapping failure. For
hot water, the cache contains only the first subset and later reads silently use
that incomplete cache.

## Goals / Non-Goals

**Goals:**

- Record lazy-validation coverage by parameter ID for sections and hot-water
  groups.
- Revalidate only the parameter IDs required by a later request when they have
  not already been covered.
- Retain the existing public method signatures, include-filter validation, and
  per-section/group locking model.
- Add regression tests for sequential filtered and unfiltered access.

**Non-Goals:**

- Change the public `include` API or make it accept parameter IDs.
- Alter device-response parsing, model serialization, or unsupported-parameter
  rules.
- Retry or cache failed validation requests.

## Decisions

### Track covered parameter IDs per validation owner

`APIValidator` will maintain a mapping from section name to the set of parameter
IDs whose support was checked. `SectionValidator` will maintain the equivalent
mapping for hot-water group names. Completion for a request is determined by
whether its requested IDs are a subset of that owner’s covered IDs.

Parameter IDs are chosen over parameter names because they are the identifiers
sent to BSB-LAN and remain unambiguous if a configuration ever aliases a name.
When a response establishes an ID is unsupported, it is removed from the active
configuration/cache but remains covered, preventing needless repeated probes.

Alternative considered: avoid persisting any completion after an `include`
request. This avoids the defect but discards useful knowledge and repeatedly
validates already checked parameters. Parameter-level coverage keeps lazy
loading efficient while remaining correct.

### Derive requested IDs before the one-time gate

Each ensure method will first resolve the configured IDs for its section or
group, applying `include` when present. Its lock’s fast and post-lock checks will
compare that specific requested-ID set to coverage rather than use a coarse
section/group marker. A full request resolves all currently configured IDs and
therefore completes only after each is covered.

An include filter that matches no IDs will not add coverage or mark a group or
section complete. Existing downstream include validation remains responsible for
returning the appropriate invalid-include error.

Alternative considered: retain a boolean for full validation plus a separate
partial set. This duplicates state and makes configuration changes harder to
reason about; one coverage mapping expresses both cases.

### Preserve locks and recheck coverage after waiting

The existing per-section and per-group locks remain in place. The completion
predicate will calculate coverage for the current requested IDs both before and
after lock acquisition. Concurrent calls requesting different subsets therefore
serialize safely, and the second call still validates its uncovered IDs.

## Risks / Trade-offs

- [Configuration mutation during validation] → Derive the requested IDs from
  the current configuration at each completion check; removed unsupported IDs
  no longer need validation.
- [Stale internal tests inspect completion sets] → Update tests to assert
  parameter coverage and externally observable request/cache behavior instead
  of obsolete whole-group completion.
- [Additional first-read requests] → A later request for previously unrequested
  parameters necessarily makes one validation request; already covered IDs are
  not re-requested.
