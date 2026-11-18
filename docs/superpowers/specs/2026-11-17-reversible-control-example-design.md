# Reversible control example

> Follow-up: [RVS21 automatic profiles](2026-11-17-rvs21-automatic-profile-design.md)
> permits a selected automatic group instead of a manual mapping. The same
> preflight, one-day restore/readback and explicit write opt-in rules apply.

## Approved behavior

Update `examples/control.py` for the current schedule API. The user approved
explicit `--write` opt-in, reading originals before writes, changing one selected
weekday and restoring it afterwards, and doing the same for the thermostat
setpoint. They additionally require HVAC mode to be restored. Keep local device
time synchronization (same timezone), without restoring the old clock.

## Approach

Use a small example-only roundtrip helper rather than adding library transaction
semantics or continuing the old permanent writes. Each setting is changed,
verified, restored in `finally`, and verified again before proceeding to another
setting. This limits the number of simultaneously modified settings to one.
Read/preflight all originals before the first write. Do not execute live device
writes while developing/testing this example.

The default invocation reads/prints only. `--write` exercises temperature (default
18 in controller units), HVAC mode (default 3/heat), and synchronizes local time
on supported buses. `--circuit {1,2}` selects the same circuit for all thermostat
reads/writes and heating schedule operations. Validate finite temperature input,
mode/circuit choices and schedule JSON/intervals before discovery.

Optional mutually exclusive `--heating-mapping` / `--hot-water-mapping` JSON flags
supply one independently confirmed weekday mapping. `--weekday` defaults to
Monday. A write demo with a mapping requires an explicit nonempty `--schedule`
interval string. A schedule target requires both a mapping and `--write`.
Without a mapping, no schedule is probed or written; without `--write`, a supplied
mapping can be inspected read-only. Never infer mappings or use diagnostic-only
candidates as automatic write authorization.

## Preflight and restoration

Require readable, error-free, writable, finite thermostat originals, a supported
bus/mode and writable originals. The permission bugfix clarifies that on BSB/LPB
`buswritable=0` is a gateway default, not an absolute veto: require explicit
per-parameter `readwrite=0` in that case, and always reject explicit read-only or
write-only originals. PPS write-off remains an absolute gateway restriction.
Check original and requested temperature against
known heating bounds (protective/min and comfort-max/max), not cooling bounds.
Only the selected schedule day must be readable, nonempty, writable and encodable
by `DaySchedule`; unrelated missing days are not overwritten. Refuse unavailable,
unparsed or empty originals because safe schedule clearing is not supported.
Validate the requested day encoding before any writes.

A roundtrip arms restoration before attempting its temporary write, so rejected
or uncertain requests still attempt to restore the saved original. Equality is
checked with a fresh public API readback, not acknowledgement alone. Skip unchanged
targets. Restore/verify in `finally`, including after ordinary cancellation. If
both the operation and restoration fail, preserve both errors in an exception
group and prominently report the original value requiring manual recovery.
Restoration is best effort, not a guarantee against disconnection, repeated
interrupts, process termination or concurrent operator/automation writes.

HVAC mode roundtrips use the library-normalized mode and retain PPS restrictions.
Schedule restoration preserves supported parsed intervals, not exact disabled
physical-slot formatting. Time synchronization occurs only after reversible demos
finish successfully and is intentionally not rolled back; unsupported buses skip
it. Read-only runs never set temperature, mode, schedules or time.

## Files and validation

Keep existing display helpers in `examples/control.py`; add
`examples/control_roundtrip.py` for typed options, preflight and roundtrip logic.
Tests mock device I/O and exercise the real CLI parser, routing, readback failures,
uncertain writes, cancellation, restoration failures and successful restores.
Update the older test that required rejecting `--circuit 2`: circuit selection is
now supported consistently rather than silently writing circuit 1.

Python 3.12+, no new dependencies or library behavior changes. Preserve all prior
uncommitted work. Run focused example safety tests, full pytest, `uv run prek run --all-files`,
CLI help and documentation build. Per the user's follow-up, no coverage target
applies to the example scripts; do not add tests just to increase their coverage. Keep changes
on the feature branch without committing, pushing or merging.
