# RVS21 integer and decimal schedule profiles

## Intent

Automatically read and write supported weekly schedules on the verified RVS21
installations without forcing users to enter weekday IDs. The immediate reported
need is decimal weekday IDs for HC1 and DHW on BSB-LAN `5.1.1-20260316232429`.

## Scope

- Keep the existing integer profile for BSB-LAN `5.0.82-20251124154226`.
- Include integer weekday mappings for HC1 (`501`–`507`), HC2 (`521`–`527`) and
  DHW (`561`–`567`).
- Add a narrowly scoped decimal profile for BSB-LAN `5.1.1-20260316232429`, BSB,
  destination 0, controller `RVS21.831F/127`, family 211, variant 127.
- In that decimal profile, HC1 uses `501`, `501.1`–`501.6`; DHW uses `561`,
  `561.1`–`561.6`; HC2 remains integer (`521`–`527`).
- Keep profile declarations group-keyed so decimal HC1/DHW are independently
  certifiable and future circuit/group mappings can be added without changing the
  resolver API.
- Require fresh active `/JC` weekday-name, TIMEPROG type, and destination checks
  plus compatible `/JQ` values; ambiguous, missing, or malformed evidence remains
  disabled/retryable. No writes occur during discovery.
- No decimal HC2 mapping is included.

## Evidence

Issue #1668 comment `7044555252` supplies the exact adapter version,
destination, controller/family/variant identity, decimal HC1 source rows, French
weekday labels, and HC1 `/JC` and `/JQ` observations. The repository owner
separately confirmed BSB as the bus type. The issue body supplies the corresponding
decimal DHW source rows but no DHW `/JC` or `/JQ` observations; runtime `/JC` checks
must verify that active layout before use. HC2 uses the requested integer IDs, but
the issue reporter supplied no HC2 rows or observations; runtime layout/value
checks gate that group.

## Approaches

1. Add separate evidence-scoped integer and decimal standard profiles and keep
   the existing per-group resolver unchanged. This preserves current cache,
   permission, and fail-closed behavior and is selected.
2. Infer ID formats from firmware or scan parameter ranges. Rejected because it
   can guess weekday roles and broaden unsupported installations.
3. Weaken incomplete-probe handling to prefer one profile. Rejected because a
   missing competing layout is not conclusive evidence.

## Validation

Tests must prove exact mappings and identities, automatic integer and decimal
selection, HC2 integer support, exact decimal IDs in reads/writes, and fail-closed
handling for wrong, incomplete, or unsupported active layouts. Update the profile
documentation and sanitized evidence fixture. Run focused tests, the full test
suite, `uv run prek run --all-files`, then request a fresh Sol 6.2 review.
