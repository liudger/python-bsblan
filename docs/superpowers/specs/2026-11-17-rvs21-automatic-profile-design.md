# RVS21 automatic schedule profile

## Intent and approved evidence

Complete the original verified-profile feature so the owner can test discovery,
read, write and restore on the real board without manual weekday configuration.
The owner confirmed that the sibling BSB-LAN firmware project supplies this
board's definitions; the board runs an older compatible build. Weekday rows are
unchanged across the local current, backup and newer definition files.

Observed installation: RVS21.831F/127, controller family 211/variant 127, BSB,
destination 0, firmware `5.0.82-20251124154226`, JSON API 2.0. A tracked upstream
version-header commit matches that exact build string, but custom definitions are
untracked: do not claim a Git commit certifies the flashed table. The owner
confirmation plus extracted controller-specific command/weekday rows establish
meaning. Live `/JC` corroborates the active layout independently of availability
probes. HC1 501..507 and DHW 561..567 are Monday..Sunday, TIMEPROG type 9,
destination 0, readwrite=0. Live `/JQ` confirmed readable values for both groups.
Only HC1 will be modified in the live test. HC2 remains unsupported by this
profile pending live evidence.

## Approach

Keep evidence-backed profiles, not guessed scans or caller manual overrides. Add
an immutable optional `ScheduleProfile.table_parameters` tuple of (ID, name)
pairs. It must cover every mapped ID exactly once, with nonempty declared names.
Profiles without this evidence still need the explicit `schedule_table` assertion.
Profiles with it may match automatically when `schedule_table` is absent.

Match controller/build/bus/destination first, then compare the predefined group's
seven `/JC` structures against its declared names, exact integer type 9 and exact
integer destination. This is recognition of an independently evidenced layout,
not assigning weekdays from returned labels. Each group is checked independently.
Only a unique fully compatible candidate may be selected; ambiguity fails closed.
Incomplete table data requests retries; wrong complete structures are incompatible;
auth/connection/malformed errors propagate. Do not select another candidate while
one eligible candidate is inconclusive. Explicit table assertions cannot be
silently overridden. Unknown installations remain disabled.

Add one narrowly scoped built-in profile for the exact observed build/controller,
HC1 and DHW. The expected labels are literal English labels in the supplied table,
not the UI language. No blanket support claim for all RVS21/firmware 5.x or the
decimal scheme in #1668. Ship sanitized evidence excerpts/structures, with no
credentials, MAC, IP or current schedule values. Runtime does not depend on the
sibling repository or access its files.

A live layout signature is not a cryptographic checksum of the whole firmware.
The API does not expose that. Document that same-signature custom changes to
underlying bus command semantics cannot be detected; reconfirm after such changes.
This refines the earlier explicit-table-only design rather than pretending the
API now exposes a table hash.

## Cache and timing

Reuse `/JC` results within one resolution/discovery call, never cache a negative
result permanently. Cache successful mappings exactly as before. Remember observed
structure facts only to detect changes; a changed previously observed signature
increments the resolver identity revision and invalidates cached group proofs.
First observation of a disjoint group's signature does not invalidate other
validated groups. Fresh automatic write preflight checks identity, layout and
availability again. No probing at import/initialize and no sleeps/background work.

## Control example

Allow `--schedule` with no mapping: it requests automatic HC1 discovery by default.
Add `--schedule-group {heating,hot-water}` for explicit automatic inspection or DHW
selection. Manual mapping flags remain supported and take precedence, with
contradictory group selections rejected locally. A write still needs `--write`;
no target means no schedule write. Default invocation remains read-only and does
not touch schedules. Unknown/unrestorable schedule data blocks all demo writes.
The existing one-day finally/restore/readback behavior remains unchanged.

## Validation and live test

Use TDD for profile scope/signature, per-group results, ambiguity/incomplete
responses, cache invalidation and CLI automatic routing. Tests that intentionally
exercise an empty registry must configure `schedule_profiles=()` explicitly.
Run full pytest and required hooks; no example coverage target.

After validation: call default `discover_schedules()` on the board, require HC1
enabled with source=profile, save the full HC1 snapshot, temporarily change only
Tuesday to 07:00-09:00, read back, restore the original 06:00-22:00 in finally and
verify the full week's parsed values are unchanged. Keep temperature/mode at their
original 18.5/3 so the example skips those changes. Time sync remains permitted.
Delete the user-only temporary credentials file after live testing completes.
