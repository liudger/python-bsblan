# cooling-operating-mode

## Purpose

Reading and setting the cooling circuit operating mode (BSB-LAN parameters `901`/`1201`) through the state model and the thermostat setter, scoped to the full API configuration.

## Requirements

### Requirement: State exposes cooling operating mode
The `State` model SHALL include an optional `cooling_operating_mode` field populated from BSB-LAN parameter `901` (circuit 1) or `1201` (circuit 2) when the full API configuration is active and the device reports the parameter.

#### Scenario: Read cooling operating mode for circuit 1
- **WHEN** `state()` is called on a full-config device that exposes parameter `901`
- **THEN** the returned `State.cooling_operating_mode` contains the parameter's name, value, and unit

#### Scenario: Read cooling operating mode for circuit 2
- **WHEN** `state(circuit=2)` is called on a full-config device that exposes parameter `1201`
- **THEN** the returned `State.cooling_operating_mode` reflects parameter `1201`

#### Scenario: Device without cooling support
- **WHEN** `state()` is called on a device where parameter `901` is absent or inactive (`"---"`)
- **THEN** section validation drops the parameter and `State.cooling_operating_mode` is `None`
- **AND** no error is raised

#### Scenario: Basic configuration excludes cooling
- **WHEN** the client resolves the basic (single-circuit) configuration
- **THEN** parameter `901` is not requested and `State.cooling_operating_mode` is `None`

### Requirement: Thermostat can set cooling operating mode
The `thermostat()` method SHALL accept an optional `cooling_operating_mode` argument and send it as a single `/JS` request to parameter `901` (circuit 1) or `1201` (circuit 2).

#### Scenario: Set cooling operating mode for circuit 1
- **WHEN** `thermostat(cooling_operating_mode=1)` is called
- **THEN** the client sends one `/JS` request with `Parameter` `901`, `Value` `"1"`, and `Type` `"1"`

#### Scenario: Set cooling operating mode for circuit 2
- **WHEN** `thermostat(cooling_operating_mode=0, circuit=2)` is called
- **THEN** the client sends one `/JS` request targeting parameter `1201`

#### Scenario: Only one thermostat parameter per call
- **WHEN** `thermostat(hvac_mode=3, cooling_operating_mode=1)` is called
- **THEN** `BSBLANError` is raised (existing single-parameter contract)
- **AND** no HTTP request is sent

### Requirement: Cooling operating mode values are validated
The client SHALL validate `cooling_operating_mode` against the set of values supported by the device parameter (confirmed from real-device raw data) before sending, and SHALL raise `BSBLANInvalidParameterError` for values outside that set.

#### Scenario: Invalid value rejected
- **WHEN** `thermostat(cooling_operating_mode=99)` is called
- **THEN** `BSBLANInvalidParameterError` is raised
- **AND** no HTTP request is sent

### Requirement: Cooling operating mode is unavailable on PPS bus
The client SHALL raise `BSBLANInvalidParameterError` when `cooling_operating_mode` is passed to `thermostat()` while the device operates on the PPS bus.

#### Scenario: PPS device rejects cooling operating mode
- **WHEN** the device uses the PPS bus and `thermostat(cooling_operating_mode=1)` is called
- **THEN** `BSBLANInvalidParameterError` is raised
- **AND** no HTTP request is sent
