# error-classification

## Purpose

Distinguish transport failures, local unsupported/configuration conditions,
per-day observations, and uncertain partial writes. Exception classes describe
what failed; they do not promise permanent unavailability or eventual recovery.
All library operation exceptions remain catchable as `BSBLANError`.

## Requirements

### Requirement: Missing mappings fail locally

A schedule operation SHALL raise `BSBLANScheduleMappingError` when its target
has no configured mapping. It SHALL retain the group, circuit, and reason and
SHALL NOT send a schedule request or fall back to fixed integer IDs.

Invalid mapping construction SHALL fail validation before device I/O. A missing
schedule mapping SHALL NOT prevent ordinary climate monitoring.

### Requirement: Known unsupported operations are explicit

Known PPS schedules, writes prohibited by bus metadata, and unverified schedule
clearing SHALL raise `BSBLANUnsupportedFeatureError` before schedule writes.
No unavailable day or unsupported format SHALL silently become a clear command.
This exception does not assert that reconfiguration can never change support.

### Requirement: Unavailable days are observations, not capability conclusions

A well-formed schedule response SHALL yield seven explicit day observations.
Missing IDs, inactive values, and device errors SHALL remain unavailable, with
raw values, available metadata, and error context preserved. They SHALL NOT
be converted to empty days or cached as permanent unsupported features.

The snapshot SHALL derive completeness from readable/empty day outcomes. It
SHALL advise later reads for missing/inactive values and device errors other
than code 7. That advice is not a guarantee of recovery.

### Requirement: Unsupported interval representations retain the week

A valid text entity whose interval representation is unsupported SHALL become
an `unparsed` day with its raw value retained and no writable `DaySchedule`.
It SHALL NOT discard other days or masquerade as corrupt JSON. Unsupported
representation alone SHALL NOT require endless repeated reads.

### Requirement: Corrupt responses preserve typed errors and causes

Invalid JSON, non-object /JQ envelopes, and malformed entity metadata SHALL raise
`BSBLANMalformedResponseError`. Schedule reads SHALL include group/circuit/ID
context and preserve the original decode cause and location. They SHALL NOT
include the entire response body in the outer error message.

Authentication and connection failures SHALL retain their exception types on
reads. Programming errors SHALL NOT be reclassified as unavailable observations.
Other endpoints SHALL retain their existing envelope handling and transport
retry policy SHALL remain unchanged. No exception type guarantees retry success.

### Requirement: Schedule writes report acknowledgement and uncertainty

Only an integer status 1 under the exact requested /JS parameter key SHALL count
as acknowledgement. HTTP success, string/bool statuses, and generic success
objects SHALL NOT count. Acknowledgement SHALL NOT be described as readback.

On the first rejected or uncertain write the library SHALL stop, raise
`BSBLANScheduleWriteError`, and retain acknowledged weekdays, the failed weekday
and ID, unattempted weekdays, group/circuit, and the rejected/unknown outcome.
Transport/decode failures SHALL be chained as the cause. An unknown failed-day
outcome SHALL NOT be interpreted as proof that no change occurred.

Cancellation SHALL propagate without being converted to a write rejection.
There SHALL be no implied whole-week transaction, automatic rollback, readback,
retry schedule, or state publication in the schedule API.

### Requirement: Generic library handlers remain usable

The mapping, unsupported-feature, malformed-response, authentication, connection,
and partial-write exceptions SHALL remain subclasses of `BSBLANError`.
