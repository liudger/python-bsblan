# Reusable schedule discovery and issue #1668 diagnostics

## Approved scope and approach

The user approved reusable validated profiles plus an explicit diagnostic probe
for issue #1668, with discovery timing controlled by HA. This extends the verified
profile framework, not the HA integration. A hardcoded library startup sleep and
blind fallback scanning were rejected: elapsed time is not bus-idle detection,
and readable TIMEPROG values do not prove weekday meaning.

## Positive cache and lifecycle

Keep successful automatic mapping resolutions per group in `ScheduleManager`.
Cache only immutable mapping/availability, never schedule values or negative
results. Subsequent reads fetch seven fresh values without `/JI` or controller
identity requests. Successful explicit discovery primes this cache. Cache hits
still check the captured transport target and cached adapter/bus fingerprint.
Fresh schedule responses must pass the same compatibility rules; inconclusive,
incompatible or malformed responses invalidate trust, without triggering alternate
candidate scans. Preserve manual override behavior exactly.

`discover_schedules(*, refresh: bool = False)` reuses validated groups by default;
`refresh=True` discards cached trust before refreshing. Unknown/retry/incompatible
groups are never negatively cached. `invalidate_schedule_profiles()` synchronously
clears automatic trust without I/O; HA can call it on reconnect/reload or when it
knows installation/table configuration changed. Exhausted transport connection
failures also clear trust. Cached metadata changes invalidate all positive entries.
A new client is still required to change configured mappings/profiles/table.

Automatic writes always perform fresh identity matching and a seven-ID probe,
even with a cached mapping. Preserve target/bus/writability checks and partial
write reporting; explicit invalidation between day writes stops further commands.
An asyncio lock serializes discovery/resolution/diagnostic work and coalesces
concurrent successful first-use resolution. A generation counter prevents a
cancelled or explicitly invalidated in-flight discovery from publishing stale
trust. No cache TTL, persistent cache, background tasks or sleeps are added.
The cache cannot detect unreported remote controller/table changes.

## Bounded issue #1668 diagnostic

Add `probe_schedule_candidate("issue_1668_dhw") -> ScheduleCandidateProbe`.
The only candidate is DHW Monday `561`, Tuesday through Sunday `561.1`–`561.6`,
with provenance `https://github.com/liudger/python-bsblan/issues/1668`. The issue
supplies custom table rows scoped to controller family 211/variant 127; the linked
HA report describes an Atlantic/Siemens RVS21 installation. This is diagnostic
candidate evidence, not proof of the caller's active table.

The opt-in probe refreshes `/JI` to require an explicit BSB/LPB bus, then reads
only those seven exact IDs via `/JQ`. It performs no controller-identity scan,
`/JS` write or automatic fallback. Reject unknown candidate IDs locally and known
PPS before network I/O. Reuse normal compatibility classification and retain
incompatible/retry parameter IDs in the result. Network/auth/malformed failures
retain their exceptions. No diagnostic result populates the automatic cache or
enables a group, even when all parameters are compatible.

`ScheduleCandidateProbe` is immutable and exposes candidate ID, evidence URL,
proposed mapping, compatibility status (`compatible`, `incompatible`, `retry`),
parameter-level incompatible/retry IDs, `enabled=False`,
`requires_confirmation=True`, and `retry_required`. Confirmed active-table evidence
can be used separately to configure a manual override; do not silently promote
this diagnostic candidate into a standard profile.

## HA timing guidance

Document the sequence: finish initial climate reads, schedule discovery at least
15 seconds later, and coordinate it with polling so requests do not overlap.
Do not await that delay in integration setup. Cancel the task on unload, handle
integration reloads after HA is already running, and retry transient failures
without mapping repairs. HA owns the scheduling/queue; the library cannot observe
all physical bus traffic. The new lock only serializes profile-related work.

## Constraints and verification

Python 3.12+, API v3 baseline, no new dependencies or HA Core changes. Keep the
standard profile registry empty pending independently reviewed installation
scope. Preserve caller-confirmed overrides and all existing write safety gates.
Use TDD for cache lifecycle, invalidation races, cancellation, single-flight,
manual precedence, fresh write preflight and issue-specific exact decimal IDs.
Run full pytest (>=95% total, 100% modified executable coverage), required
`uv run prek run --all-files`, and strict documentation build. Keep all existing
uncommitted work and unrelated user files intact; do not push or merge.
