# Design: add-cooling-operating-mode

## Context

BSB-LAN param `901` (CC1) / `1201` (CC2) is the cooling circuit operating mode — the on/off/auto control for cooling, separate from heating `hvac_mode` (`700`/`1000`) and the read-only changeover status (`900`/`1200`, already mapped). Verified present on a real RVS21.831F device. The library reads heating-section params through the lazily validated `APIConfig` sections and writes via `thermostat()`, which resolves parameter IDs per circuit from `CircuitConfig.THERMOSTAT_PARAMS` and sends one `/JS` request per populated argument.

## Goals / Non-Goals

**Goals:**

- Read `cooling_operating_mode` as part of `state()` for both circuits (full config).
- Set it via `thermostat(cooling_operating_mode=...)` for circuits 1 and 2.
- Validate values client-side before sending.

**Non-Goals:**

- Basic (single-circuit) config and PPS bus support — cooling is deliberately excluded from those profiles.
- Home Assistant integration changes (downstream; this only unblocks them).
- Any changes to changeover (`900`/`1200`) or cooling setpoints (`902`/`1202`) behavior.

## Decisions

1. **Naming: `cooling_operating_mode`** (not `cooling_hvac_mode`). It matches the BSB-LAN label "Operating mode" and avoids implying it is a full HVAC mode; follows the existing `operating_mode` precedent in hot-water params. Alternative `hvac_mode_cooling` rejected — the `hvac_mode*` prefix family is reserved for the heating/changeover trio.

2. **Read path: add to heating sections.** `"901": "cooling_operating_mode"` in `BASE_HEATING_PARAMS`, `"1201"` in `BASE_HEATING_CIRCUIT2_PARAMS`. Per-section validation already drops parameters absent on a device (same mechanism as boost `770`/`1070`), so heat-only devices degrade gracefully. Not added to `BASIC_HEATING_PARAMS` or `PPS_HEATING_PARAMS`.

3. **Model type: follow real-device raw data.** First implementation step queries `901` via `examples/fetch_param.py`. Expected: enum with integer value (like `700`) → `EntityInfo[int] | None`. If `data_type` turns out unknown/ambiguous, fall back to `EntityInfo[str] | None` per repo convention. Field is optional so existing fixtures stay valid.

4. **Write path: extend `thermostat()`.** Add optional `cooling_operating_mode: int | None = None`; add `"cooling_operating_mode": "901"` / `"1201"` to `CircuitConfig.THERMOSTAT_PARAMS`. Reuses the existing one-`/JS`-per-parameter loop and `_set_payload` helper, and joins the existing `_validate_single_parameter` contract (exactly one thermostat parameter per call). Alternative — a separate `cooling()` method — rejected: `thermostat()` is the established multi-parameter setter and HA calls it already.

5. **PPS guard.** `_get_pps_thermostat_params()` has no cooling entry; if `cooling_operating_mode` is passed while on PPS bus, raise `BSBLANInvalidParameterError` (explicit, instead of silent `KeyError`).

6. **Validation: dedicated value set.** New `Validation.COOLING_OPERATING_MODES` constant checked in a `_validate_cooling_operating_mode` step mirroring `_validate_hvac_mode`. The exact enum values must be read from the device raw response (`possibleValues`); do not reuse `HVAC_MODES = {0,1,2,3}` blindly.

## Risks / Trade-offs

- [Enum values unconfirmed until device query] → First task fetches raw data for `901`/`1201`; constants set from evidence, not guesses.
- [Setter usable on basic-config devices where `901` may not exist] → Parity with existing behavior for `902` (`target_temperature_high`): the device rejects unknown params; no extra capability guard added. Documented limitation.
- [HC2 values return `"---"` on devices with nothing connected] → Already handled by `is_param_value_active`-style probe/validation logic; read simply omits the field.

## Open Questions

- ~~Exact `possibleValues` for `901`~~ **Resolved 2026-07-02** via `/JC` on real device (RVS21.831F): both `901` and `1201` are writable ENUMs with `0=Protection, 1=Automatic, 2=Reduced, 3=Comfort` (same set as heating `hvac_mode`). Values returned as strings (`"3"`) with `dataType: 1` → model type `EntityInfo[int] | None`; valid set `{0, 1, 2, 3}`.
