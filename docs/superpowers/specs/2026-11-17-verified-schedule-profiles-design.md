# Verified schedule profile framework

> Follow-up: [reusable discovery and #1668 diagnostics](2026-11-17-schedule-discovery-reuse-design.md)
> supersedes the per-operation automatic-read reprobe policy below. Automatic
> writes retain fresh preflight; unverified candidates still never enable groups.

> Follow-up: [the verified RVS21 profile](2026-11-17-rvs21-automatic-profile-design.md)
> replaces the empty-registry/explicit-table-only stage with source-backed,
> per-group active-layout signatures. It does not infer weekday roles from labels.

## Intent and scope

Reduce Home Assistant schedule setup to automatic profile matching and read-only
compatibility checks, while retaining explicit weekday mappings as overrides.
This change is in python-bsblan; HA owns repair presentation and retry scheduling.
The user accepted implementing the framework without promoting uncertified example
mappings. No verified installation evidence is currently available in this repo.

## Approaches

- Guess standard IDs from firmware or readable values: rejected; neither proves
  weekday meaning or the active controller table.
- Evidence-backed profiles plus runtime probes: selected. Profiles establish day
  meaning; probes only establish availability and TIMEPROG type compatibility.
- Manual-only mappings: safe but retain the setup burden; preserve as overrides.

## Design

Add immutable public profile identity, profile and availability models in
`schedule_profiles.py`, with request orchestration in `_schedule_profiles.py`.
A profile records provenance/evidence, exact adapter firmware, bus and destination,
controller identification/family/variant, active-table identifier and mappings.
The library reads `/JI` and raw parameters `6224,6225,6226` to match the installation.
The current API models expose no trustworthy active-table identifier: optional
`BSBLANConfig.schedule_table` is a deployment assertion, not inferred from firmware.
Missing table evidence fails closed. Profiles can be supplied through config for
verified deployments; the built-in registry stays empty until evidence is reviewed.
A claimed evidence string is provenance, not independent certification by the API.

`discover_schedules()` returns independent availability for HC1, HC2 and DHW.
Manual mappings win per group without automatic probing. Otherwise, exactly one
identity-matching profile must supply that group. Ambiguity fails closed. No IDs
are scanned and no writes occur during discovery. Probes read all seven exact IDs,
require error-free text values and integer TIMEPROG type 9, but do not require the
interval codec to understand the text (e.g. midnight-ending intervals).

Missing/inactive values and non-7 device errors request retries; explicit error 7
or wrong types produce incompatibility. Connection/authentication/malformed errors
retain their exceptions, never become mapping repairs. Mixed failures prioritize
retry before incompatibility so incomplete data cannot certify a mismatch.

Schedule reads and writes lazily resolve automatic groups. Each automatic operation
refreshes identity and probes the group; reads reuse probe data. There is no
negative cache or stale automatic mapping to survive reconnects. Existing manual
read/write behavior remains unchanged. Target/metadata changes during resolution
or a sequential write abort safely. Ordinary startup/climate polling stays lazy.

Availability exposes `enabled`, `repair_required`, `retry_required`, reason,
profile ID and mapping source. Unknown/incompatible schedule operations raise
`BSBLANScheduleMappingError`; transient incomplete probes raise a separate
`BSBLANScheduleProbeError`. Network exceptions propagate for caller retries.

## Constraints and non-goals

- Python 3.12+, API v3 baseline; no new dependencies or HA Core changes.
- Preserve immutable circuit-keyed mappings, PPS rejection, sequential `/JS`
  writes, clear rejection, partial-write reporting and manual target guards.
- No built-in guessed profile, writable probe, firmware-only selection, background
  retry loop, schedule persistence or automatic destructive clearing.
- A new client is required after changing the asserted active table or profiles.

## Validation

Synthetic profiles must be explicitly labelled as test evidence. Cover exact and
mismatched identities, absent evidence, ambiguous groups, partial support, manual
precedence, missing/inactive/transient/error-7/wrong-type data, unparsed schedules,
connection recovery, automatic read/write routing, mid-flight target changes and
zero schedule I/O during startup. Run full pytest and `uv run prek run --all-files`;
maintain total coverage >=95% and cover every changed executable line.
