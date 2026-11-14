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

## BSBLANScheduleWriteError

::: bsblan.BSBLANScheduleWriteError

A partial/uncertain write is not rolled back. Inspect acknowledged, failed and
unattempted days, then perform explicit readback; see the
[migration guide](../schedule-migration.md#acknowledgement-partial-writes-and-readback).
