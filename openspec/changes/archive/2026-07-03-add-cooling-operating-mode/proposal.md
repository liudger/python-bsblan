# Proposal: add-cooling-operating-mode

## Why

BSB-LAN exposes a separate operating mode for the cooling circuit (parameter `901` for circuit 1, `1201` for circuit 2), distinct from the heating operating mode (`700`/`1000`) and the heating/cooling changeover status (`900`/`1200`). The library currently has no read or write support for it, which blocks Home Assistant from offering an explicit COOL HVAC mode — users can read cooling setpoints (`902`/`1202`) but cannot see or control whether cooling is enabled.

## What Changes

- Add parameter mapping `901` → `cooling_operating_mode` (circuit 1) and `1201` → `cooling_operating_mode` (circuit 2) to the full API configuration (heating sections).
- Add `cooling_operating_mode` field to the `State` response model.
- Extend the `thermostat()` setter to accept a `cooling_operating_mode` argument, sending one `/JS` request per populated parameter (existing convention), for both circuits.
- Validate the accepted value range for `901`/`1201` before sending (verified against real-device raw data via `examples/fetch_param.py`).
- Excluded from scope: the basic (single-circuit) configuration and PPS bus — cooling is intentionally not part of those profiles.

## Capabilities

### New Capabilities

- `cooling-operating-mode`: Reading and setting the cooling circuit operating mode (params `901`/`1201`) through the state model and the thermostat setter, scoped to the full API configuration.

### Modified Capabilities

<!-- No existing specs in openspec/specs/ — nothing to modify. -->

## Impact

- `src/bsblan/constants.py`: `BASE_HEATING_PARAMS`, `BASE_HEATING_CIRCUIT2_PARAMS`, `CircuitConfig.THERMOSTAT_PARAMS`, validation constants for the new value range.
- `src/bsblan/models.py`: `State` model gains `cooling_operating_mode`.
- `src/bsblan/bsblan.py`: `thermostat()` signature and set logic, parameter validation.
- `tests/`: new/extended tests for state read, setter, and validation (coverage gates: total ≥ 95%, patch 100%).
- Docs: README + docs feature listing per repo convention.
- No breaking changes; new field/argument are optional.
