## Why

In python-bsblan 6.1.6 both an *unsupported schedule* (a device that will never
return the requested time-program parameters) and a *malformed response* (a
transient decode/parse failure) are surfaced as the same generic `BSBLANError`.
Downstream integrations such as Home Assistant cannot tell them apart by
exception type, so they must choose between stopping retries on a transient
malformed response or retrying an unsupported schedule indefinitely after a
write. A dedicated exception taxonomy is needed at the library level to make the
permanent-vs-transient distinction explicit.

## What Changes

- Add a dedicated **permanent** exception `BSBLANUnsupportedFeatureError`
  (subclass of `BSBLANError`) raised when a device does not expose the requested
  schedule parameters, so callers know retrying will never succeed.
- Add a dedicated **transient** exception `BSBLANMalformedResponseError`
  (subclass of `BSBLANError`) raised when a response body cannot be decoded or
  parsed as valid JSON, signalling that a retry may succeed.
- Raise `BSBLANUnsupportedFeatureError` in the heating- and hot-water-schedule
  read paths where a bare `BSBLANError` is currently raised for absent schedule
  parameters.
- Raise `BSBLANMalformedResponseError` in the transport layer where invalid
  JSON / decode errors are currently wrapped in a bare `BSBLANError`.
- Both new exceptions subclass `BSBLANError`, so existing `except BSBLANError`
  handlers keep working (non-breaking).

## Capabilities

### New Capabilities
- `error-classification`: A library exception taxonomy that distinguishes
  permanent unsupported-feature failures from transient malformed-response
  failures, letting callers make correct retry decisions.

### Modified Capabilities
<!-- No existing spec's requirements change; client-retry-policy behavior is unaffected. -->

## Impact

- `src/bsblan/exceptions.py`: two new exception classes.
- `src/bsblan/_schedules.py` and `src/bsblan/_hot_water.py`: raise the new
  unsupported-feature error for absent schedule parameters.
- `src/bsblan/_transport.py`: raise the new malformed-response error for
  decode/parse failures.
- `src/bsblan/constants.py`: no new messages required; existing `ErrorMsg`
  entries are reused.
- `tests/`: new coverage asserting the specific exception types are raised.
- Public API: additive only. Consumers relying on `BSBLANError` are unaffected;
  consumers can opt into finer-grained handling.
