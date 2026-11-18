# Exceptions

Custom exceptions raised by the library.

## BSBLANError

::: bsblan.BSBLANError

## BSBLANConnectionError

::: bsblan.BSBLANConnectionError

## BSBLANAuthError

::: bsblan.BSBLANAuthError

## BSBLANUnsupportedFeatureError

::: bsblan.BSBLANUnsupportedFeatureError

## BSBLANMalformedResponseError

::: bsblan.BSBLANMalformedResponseError

## BSBLANScheduleMappingError

::: bsblan.BSBLANScheduleMappingError

## BSBLANScheduleProbeError

::: bsblan.BSBLANScheduleProbeError

An automatic compatibility probe was inconclusive. Retry discovery rather than
opening a wrong-mapping repair. Connection, authentication and malformed-response
errors continue to propagate as their existing exception types.

## BSBLANScheduleWriteError

::: bsblan.BSBLANScheduleWriteError

A partial/uncertain write is not rolled back. Inspect acknowledged, failed and
unattempted days, then perform explicit readback; see the
[migration guide](../schedule-migration.md#acknowledgement-partial-writes-and-readback).
