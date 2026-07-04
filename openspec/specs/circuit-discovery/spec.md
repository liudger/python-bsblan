# circuit-discovery

## Purpose

Heating-circuit discovery behavior of the BSB-LAN client: how
`get_available_circuits()` decides which circuits exist, how the basic
single-circuit configuration short-circuits probing, and the single shared
predicate that decides whether a parameter value is active — so discovery and
section validation never disagree.

## Requirements

### Requirement: Basic-config devices skip circuit probing

When the resolved API capability is the basic single-circuit configuration
(`_supports_full_config is False`), `get_available_circuits()` SHALL NOT probe
any circuit parameters and SHALL report exactly circuit 1 (return `[1]` and
set `_available_circuits = {1}`). The guard MUST be driven by the capability
flag that selects the basic configuration, not by comparing the reported
JSON-API version string.

#### Scenario: JSON-API version 1.2 (basic-config range) skips discovery

- **WHEN** `_supports_full_config` is `False` and `_json_api_version` is
  `"1.2"` and `get_available_circuits()` is called
- **THEN** no parameter requests are made, the method returns `[1]`, and
  `_available_circuits` is `{1}`

#### Scenario: JSON-API version 1.0 keeps skipping discovery

- **WHEN** `_supports_full_config` is `False` and `_json_api_version` is
  `"1.0"` and `get_available_circuits()` is called
- **THEN** no parameter requests are made, the method returns `[1]`, and
  `_available_circuits` is `{1}`

#### Scenario: Full-config device probes circuits unchanged

- **WHEN** `_supports_full_config` is `True` and `get_available_circuits()`
  is called
- **THEN** each circuit in `CircuitConfig.PROBE_PARAMS` is probed and
  circuits with an active operating-mode value are reported

#### Scenario: Unresolved capability probes circuits unchanged

- **WHEN** `_supports_full_config` is `None` (discovery called before
  capability resolution) and `get_available_circuits()` is called
- **THEN** discovery probes circuits exactly as it does today (no
  short-circuit)

### Requirement: Single shared active-value predicate

The library SHALL provide a single helper `is_param_value_active(param)` in
`utility.py` that determines whether a parameter payload carries an active
value: the payload MUST be non-empty and its `value` MUST NOT be `None` or
the inactive marker sourced from `CircuitConfig.INACTIVE_MARKER`.
`APIValidator._is_valid_param`, the heating-circuit probe loop in
`get_available_circuits`, and `_get_available_pps_circuits` SHALL all use
this helper.

#### Scenario: Active value accepted

- **WHEN** `is_param_value_active({"value": "1", "unit": "", "desc":
  "Automatic"})` is evaluated
- **THEN** it returns `True`

#### Scenario: Inactive marker rejected

- **WHEN** the parameter payload has `value` equal to `"---"` or `None`, or
  the payload is empty/`None`
- **THEN** `is_param_value_active` returns `False`

#### Scenario: Validation and discovery agree

- **WHEN** a probe parameter response would be rejected by
  `APIValidator._is_valid_param`
- **THEN** circuit discovery rejects the same response (both paths delegate
  to `is_param_value_active`)
