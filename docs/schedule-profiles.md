# Evidence-backed schedule profiles

Schedule setup can use a profile instead of entering seven weekday IDs for every
heating/DHW group. **Profiles establish weekday meaning; runtime probes only
check compatibility.** Matching names, firmware versions or seven readable
TIMEPROG parameters are not evidence of weekday assignments.

## Current support and defaults

`STANDARD_SCHEDULE_PROFILES` includes the narrowly scoped
[verified RVS21 profile](#verified-rvs21-profile) below. Matching installations can
enable HC1 and DHW without manual weekday mappings or a `schedule_table` option.
Unknown installations/groups stay disabled; ordinary climate monitoring is
unaffected. Use `schedule_profiles=()` to disable automatic profile selection.

Verified deployments can supply `BSBLANConfig.schedule_profiles`. Each immutable
`ScheduleProfile` records an ID, an evidence reference, an exact
`ScheduleProfileIdentity` and circuit-keyed `ScheduleMappings`. Supplying a
profile asserts its evidence; the library cannot independently certify an
arbitrary evidence string. Existing `schedule_mappings` remain explicit manual
overrides and take precedence **per group**, without automatic probes.

## Verified RVS21 profile

Profile ID: `rvs21-211-127-integer-20251124`.

- Controller: `RVS21.831F/127`, family **211**, variant **127**.
- Adapter build: **`5.0.82-20251124154226`**, BSB, destination **0**.
- HC1: Monday–Sunday **501–507**; DHW: Monday–Sunday **561–567**.
- HC2 and other builds/buses/variants are not certified by this entry.

The installation owner confirmed the firmware project's provenance. Its current,
backup and newer custom definition files agree on these weekday-to-command rows.
The backup source SHA256 is
`c970902ed43ea84ba1f8a1dfcce896b1067805f71c10e45b830c0789dd1847f6`.
Live `/JC` corroborated all fourteen names, integer TIMEPROG types, destination 0
and read/write flags, and `/JQ` confirmed readable values for both groups. The
sanitized `tests/fixtures/rvs21_schedule_profile.json` records source command IDs,
roles and observed scope without credentials, addresses or current programs.
An authorized live test on 2026-11-17 selected this profile with the default
registry and no manual mapping/table assertion, then changed and restored one HC1
day. Fresh readback verified all seven parsed and raw day values were restored,
with thermostat settings unchanged. DHW discovery/reads were verified; DHW was
not modified. No private program values or credentials are recorded in fixtures.
The firmware version-header commit is **not** a checksum of the untracked custom
table; no such claim is made.

This supports the observed older build without requiring a firmware upgrade. It
does not broadly certify firmware 5.x, all RVS21 installations, or the decimal-ID
table from issue #1668. Add broader scope only after independent verification.

## Installation identity

An automatic profile matches all these facts exactly:

| Identity field     | Source                                                             |
| ------------------ | ------------------------------------------------------------------ |
| `firmware_version` | Fresh `/JI` adapter version                                        |
| `bus`              | Fresh `/JI`, explicitly `BSB` or `LPB`                             |
| `destination`      | Fresh `/JI` `busdest`                                              |
| `controller`       | Raw parameter `6224`, error-free STRING (7)                        |
| `family`           | Raw parameter `6225`, error-free PLAIN_NUMBER (0), integer         |
| `variant`          | Raw parameter `6226`, error-free PLAIN_NUMBER (0), integer         |
| `table`            | Source-backed layout match, or explicit `schedule_table` assertion |

The raw `/JI` `busdest` must be an integer: booleans, floating-point values and
numeric strings are rejected before device-model coercion can turn them into a
supported destination. Malformed device metadata raises
`BSBLANMalformedResponseError` and invalidates automatic mapping trust without
publishing the invalid identity. Missing/null destinations remain unspecified,
not destination zero, and cannot activate a profile.

**The API does not expose a cryptographic identity/checksum of the full active
table.** Firmware alone is not a substitute. Profiles may declare immutable
`table_parameters`: (parameter ID, expected name) pairs covering every mapped ID
exactly once. For a matching controller/build, the resolver reads the selected
group's seven `/JC` structures and requires the predefined names, exact integer
TIMEPROG type 9 and exact integer destination. The source establishes roles;
returned labels are compared with that known layout, never sorted/interpreted to
invent a mapping.

Profiles without a declared layout still require an independently verified
`BSBLANConfig.schedule_table` assertion; otherwise they return `table_unknown`
without network probes. An explicit incompatible table assertion is never silently
overridden by automatic selection. Declared layouts are checked even when an
explicit matching assertion exists.

A signature recognizes a supported interface, not arbitrary/custom firmware
semantics. A custom table that changes bus command meanings while retaining the
same names/types/IDs cannot be distinguished by this API. Reconfirm after such
changes; recreate the client when changing configured profiles/table assertions.

Missing identity responses and temporary device errors request retries. Unknown
or unsupported identity facts cannot match. Multiple matching profiles supplying
the same group are ambiguous and fail closed, even if their mappings agree.
Profiles sharing an identity may certify disjoint groups without ambiguity.

## Discover and use schedules

For a supported installation, no weekday configuration is required:

```python
from bsblan import BSBLAN, BSBLANConfig

config = BSBLANConfig(host="YOUR_BSBLAN_IP")

async with BSBLAN(config) as client:
    for group in await client.discover_schedules():
        print(group.kind, group.circuit, group.status, group.reason)
        if group.enabled and group.kind == "heating":
            snapshot = await client.heating_schedule(circuit=group.circuit)
```

`discover_schedules()` returns HC1, HC2 and DHW availability in that order. It
reuses previously validated automatic groups. For uncached groups, it reads
identity once, verifies any declared `/JC` layout, and probes the matching group's
seven exact IDs with `/JQ`. It
never writes, scans possible IDs, resets a program, or reads unrelated parameters.
Groups absent from a matching profile remain disabled.
Manual groups are reported enabled without fetching or probing their mappings.
Known PPS metadata disables all schedule groups, including manual overrides.

A probe requires seven error-free, active text values with exact integer
`dataType=9` (TIMEPROG). It does not interpret descriptions or infer weekday roles.
Unsupported interval text (for example `06:00-24:00`) can pass compatibility while
remaining `unparsed` in a subsequent `ScheduleSnapshot`: codec support and mapping
compatibility are separate questions.

Existing readers and setters automatically perform resolution when their group
has no manual override. A first automatic read reuses probe data as its fresh
snapshot. Later reads reuse the validated mapping but still read all seven fresh
values, without repeating `/JI` or controller identity requests. Every automatic
setter performs a **fresh identity match and compatibility preflight**, even when
the mapping is cached, before normal sequential-write safety checks.

### Cache lifetime and explicit refresh

Only successful mappings/availability are cached in memory for the client
lifetime. No schedule values, negative outcomes or diagnostic candidates are
cached. Fresh layout/value permission proofs are not stored in the mapping cache.
There is no TTL or background refresh. Cached reads still check the
captured target and observed adapter/bus fingerprint, and verify compatibility of
the fresh values they receive. Incomplete/incompatible/malformed automatic reads
discard trust; later attempts can retry discovery rather than using stale proof.

- `await client.discover_schedules(refresh=True)` clears cached automatic trust
  **before** fresh discovery. A failed refresh never restores an old proof.
- `client.invalidate_schedule_profiles()` clears trust synchronously, with no
  network requests. Use it when reconnecting or when the consumer knows the
  installation changed. Discovery can then be scheduled for a quiet time.
- Observed adapter/bus metadata changes and exhausted transport connection
  failures also discard trust. Manual overrides are unaffected by cache clearing.
- A new client is required to change configured profiles, mappings or the asserted
  active table. The cache cannot detect unreported remote controller/table
  changes; arrange explicit refresh/invalidation when appropriate.

Profile resolution, discovery and diagnostic probes share an asyncio lock.
Concurrent successful first-use resolution is shared instead of duplicating
identity/probe requests. Cancellation or explicit invalidation during an await
cannot publish stale/partial trust. The lock does **not** serialize ordinary
climate polling or all physical bus traffic.

## Home Assistant: timing discovery on a slow bus

Nothing probes schedules at import, client construction or ordinary
initialization. HA controls when to call discovery. Avoid calling schedule readers
or setters before the intended discovery window: an uncached automatic operation
would trigger lazy discovery immediately.

Recommended integration lifecycle (guidance, not HA code shipped by this library):

```text
Initial climate reads complete
    -> schedule a background callback at least 15 seconds later
    -> coordinate with the polling/request queue so discovery does not overlap
    -> await client.discover_schedules()
    -> expose compatible groups; retry pending groups later
```

Do not wait for this delay inside integration setup or the initial coordinator
refresh. On initial HA boot, account for startup completion; on integration reload
when HA is already running, schedule after that entry's initial reads. Cancel any
pending callback/task on entry unload. Retry temporary failures later without a
wrong-mapping repair. A 15-second delay alone is not proof of an idle bus; all
requests from this HA client need to participate in the consumer's queue, and
other clients may still produce traffic.

A full uncached discovery can read three controller identity parameters plus up
to 21 weekday parameters. Batching into a few HTTP requests does not eliminate the
underlying bus load. Once discovery succeeds, normal reads no longer repeat the
identity work. Call invalidation rather than eager discovery on reconnect if the
consumer needs to defer that traffic again.

## Issue #1668: explicit diagnostic candidate

The [issue report](https://github.com/liudger/python-bsblan/issues/1668) supplies
custom-table rows for family **211**, variant **127**, with DHW Monday at `561` and
Tuesday through Sunday at `561.1`–`561.6`. The linked HA report describes an
Atlantic/Siemens RVS21 installation. This is useful candidate evidence, not proof
that the same table is active on another installation.

```python
result = await client.probe_schedule_candidate("issue_1668_dhw")
print(result.status)  # compatible / incompatible / retry
print(result.incompatible_parameters, result.retry_parameters)
print(result.enabled, result.requires_confirmation)  # always False, True
```

This explicit call refreshes `/JI` to require BSB/LPB, then performs one `/JQ`
request for exactly `561,561.1,561.2,561.3,561.4,561.5,561.6`. It never writes,
reads controller identity parameters, scans ranges, enables groups or promotes a
candidate into the validated-profile cache. Unknown candidate names fail locally;
known PPS is rejected before network requests. Transport/auth/malformed failures
keep their exceptions; missing/inactive/transient parameters produce retry advice.

A default profile failure or timeout does **not** automatically run this probe.
HA can offer it as a bounded diagnostic action, or explicitly schedule it after a
conclusive incompatibility. Even a `compatible` result still requires independent
active-table/weekday confirmation before configuring `ScheduleMappings` with the
returned `result.mapping`. Recreate the client after setting such a manual
override. Explicit mappings preserve decimal IDs on both reads and writes,
including Tuesday `561.1` and Sunday `561.6`; they do not fall back to `562`/`567`.

## Home Assistant: repairs versus retries

| Status         | Meaning                                                       | Consumer action                                  |
| -------------- | ------------------------------------------------------------- | ------------------------------------------------ |
| `enabled`      | Manual override or uniquely matched, compatible profile       | Enable that group                                |
| `unknown`      | Missing evidence/profile, ambiguity or unsupported identity   | Disable; offer repair/manual override            |
| `incompatible` | Complete probe proves a wrong type or unsupported parameter 7 | Disable; offer repair/manual override            |
| `retry`        | Missing/inactive values or possibly transient device errors   | Keep pending; retry, **no wrong-mapping repair** |

`ScheduleAvailability` exposes `enabled`, `repair_required`, `retry_required`,
`reason`, `source` (`manual`/`profile`) and `profile_id`. Availability is not proof
that all intervals can be edited, the parameter permits writes, or a later write
succeeded.

### Parameter permissions versus gateway defaults

BSB-LAN uses `readwrite=0` for readable/writable parameters, `1` for read-only,
and `2` for write-only. These are permission codes, not boolean writable flags.
`EntityInfo.read_write_permission` returns `True`, `False`, or `None` when the
flags are absent; model default zeros do not constitute permission evidence.
Legacy `readonly=0` is also affirmative; contradictory or malformed flags never
grant permission. Permission fields require integer values, not strings/booleans.

The `/JI` `buswritable` indicator is derived from default settings. On BSB/LPB,
active-table parameters can still be writable when it is zero. Schedule writers
therefore require explicit per-parameter read/write proof in that case, reusing
fresh automatic-probe metadata or reading `/JC` for the exact populated IDs.
Every populated day is checked before the first `/JS`. Fresh `/JC` layout and
`/JQ` value permissions are combined: an explicit denial from either response
wins, even when the other omits flags or permits writes and gateway defaults are
enabled. Complete update validation, no-op rejection and interval encoding happen
locally before automatic discovery or any other update I/O.

Each actual schedule write attempt, including backoff retries, rechecks the
captured target, cached installation metadata and permission proof; automatic
mappings additionally recheck their profile generation/layout scope. A revoked
proof aborts before the retry rebuilds its destination. Normal unchanged-target
retries remain bounded and supported. Attempt guards are task/client-local and
are unwound on failures and cancellation, so unrelated reads are unaffected.
Caller-confirmed mappings with enabled defaults retain their existing request
pattern; the device still controls write acceptance. PPS schedules remain
unsupported, and PPS thermostat writes retain the gateway-wide enable check.
These checks never invert the meaning of `/JI` or override read-only parameters.

For upstream flag definitions and default-versus-individual evaluation, see
[BSB-LAN definitions](https://github.com/fredlcore/BSB-LAN/blob/0a53c30ba499ba7ac14273fd4f56b2bf143e50df/BSB_LAN/BSB_LAN_defs.h#L71-L79)
and [parameter permission evaluation](https://github.com/fredlcore/BSB-LAN/blob/0a53c30ba499ba7ac14273fd4f56b2bf143e50df/BSB_LAN/BSB_LAN.ino#L1282-L1293).

Connection, authentication and malformed-response exceptions propagate unchanged;
they do **not** become mapping repairs. Existing HTTP retries still apply. The
consumer owns later retry scheduling and should distinguish authentication
problems from temporary connectivity. There is no permanent negative cache.
Incomplete data takes precedence over mismatches in a partially returned probe.

Schedule operations raise `BSBLANScheduleMappingError` for unknown/incompatible
mappings. Inconclusive probes instead raise **`BSBLANScheduleProbeError`**, with
`kind`, `circuit` and `reason`; retry these rather than opening a wrong-mapping
repair. HA owns rendering repairs and collecting manual overrides; this library
does not call HA APIs. After an override, recreate the client.

Host, port or passkey changes invalidate the captured target. Cached adapter/bus
metadata changes during automatic probes, between sequential writes or during
retry backoff also stop the operation. These guards are not a concurrent-reconfiguration API or proof
against unreported remote controller/table changes.

## Adding a standard profile

Before adding an entry to `STANDARD_SCHEDULE_PROFILES`:

1. Record exact controller identification/family/variant, BSB/LPB destination,
   adapter build and the **active** table/configuration. Link a stable source
   revision or fixture; redact credentials and unnecessary personal data.
2. Establish every weekday assignment independently using the controller display,
   controller documentation and confirmed active table. A source table alone does
   not prove it is active. Do not copy the synthetic test profiles.
3. Query the real device read-only with `examples/fetch_param.py`: capture raw
   identity and all proposed weekday IDs, including `/JC` structures as needed.
   Verify exact response keys, availability and TIMEPROG types. Do not use the
   `--write` mode of `examples/control.py` to gather evidence. That example is
   read-only by default and offers best-effort write/readback/restore demos only
   after explicit opt-in; see [reversible controls](getting-started.md#reversible-control-example).
4. Store the evidence reference in the profile and document its supported scope.
   Include only independently confirmed groups; HC1 support does not imply HC2
   or DHW support. Do not guess missing mappings or broaden firmware/table scope.
5. Add matching/mismatch and compatibility tests, plus sanitized evidence
   fixtures. Run full pytest and `uv run prek run --all-files`.

The first verified profile is deliberately narrow. Further profiles need the same
source provenance and active-layout evidence; readable values or a matching
firmware string alone are not sufficient.
