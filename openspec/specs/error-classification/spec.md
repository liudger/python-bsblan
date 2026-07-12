# error-classification

## Purpose

A library exception taxonomy that distinguishes permanent unsupported-feature
failures from transient malformed-response failures, letting callers make
correct retry decisions. Both new exceptions subclass `BSBLANError` so existing
broad handlers keep working.

## Requirements

### Requirement: Unsupported schedules raise a permanent error

The client SHALL raise `BSBLANUnsupportedFeatureError` (a subclass of
`BSBLANError`) when a schedule read cannot proceed because the device exposes no
schedule parameters for the requested feature. This error MUST signal a
permanent condition so callers know that retrying the same request will never
succeed.

#### Scenario: Heating schedule parameters absent

- **WHEN** `heating_schedule()` is called for a circuit whose time-program
  parameters are not present in the device response (no schedule parameters can
  be mapped)
- **THEN** the client raises `BSBLANUnsupportedFeatureError`
- **AND** the raised exception is also an instance of `BSBLANError`

#### Scenario: Hot water schedule parameters absent

- **WHEN** `schedule()` is called on a device that exposes no hot-water
  time-program parameters after include filtering
- **THEN** the client raises `BSBLANUnsupportedFeatureError`
- **AND** the raised exception is also an instance of `BSBLANError`

### Requirement: Malformed responses raise a transient error

The client SHALL raise `BSBLANMalformedResponseError` (a subclass of
`BSBLANError`) when a device response body cannot be decoded or parsed as valid
JSON. This error MUST signal a transient condition so callers know that a retry
may succeed.

#### Scenario: Response body is not valid JSON

- **WHEN** a request receives an HTTP `200` response whose body cannot be parsed
  as JSON
- **THEN** the client raises `BSBLANMalformedResponseError`
- **AND** the raised exception is also an instance of `BSBLANError`

### Requirement: New exceptions preserve backward compatibility

Both `BSBLANUnsupportedFeatureError` and `BSBLANMalformedResponseError` SHALL
subclass `BSBLANError` so that existing `except BSBLANError` handlers continue to
catch them without modification.

#### Scenario: Existing broad handler still catches new errors

- **WHEN** code catches `BSBLANError` around a call that raises either
  `BSBLANUnsupportedFeatureError` or `BSBLANMalformedResponseError`
- **THEN** the exception is caught by the `BSBLANError` handler
