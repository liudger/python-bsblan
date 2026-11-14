# Circuit-keyed schedule mappings

## Approved direction

Replace `ScheduleMappings.heating_1` / `heating_2` with a circuit-keyed heating
collection. Keep `heating_schedule(circuit=...)` and its setter unchanged. The
user approved this cleaner shape and updating the existing PR.

```python
ScheduleMappings(
    heating={1: confirmed_mapping_1, 2: confirmed_mapping_2},
    hot_water=confirmed_dhw_mapping,
)
```

Configuration associates profiles with circuit identifiers; operations select
those same identifiers. The resolver indexes the collection directly, without
constructing attribute names.

## Alternatives

- **Selected:** a circuit-keyed collection under `heating`, retaining the flat
  client interface. It expresses a collection directly and keeps existing
  operation signatures.
- **Rejected:** individually numbered fields plus dynamic `getattr` lookup;
  they duplicate the circuit identity in the configuration schema.
- **Deferred:** circuit-bound objects; eliminating the circuit argument would
  require a broader API change not needed for this cleanup.

## Constraints and behavior

- Python 3.12+; no new dependencies.
- Response/configuration models use pydantic; update payloads remain dataclasses.
- Preserve `snake_case`, existing parameter names, and all schedule safety gates.
- Support circuit identifiers 1 and 2 only; do not infer new device capabilities.
- Accept exact integer keys 1/2 and canonical JSON keys "1"/"2"; normalize to int.
- Reject bool/float keys, unsupported IDs, noncanonical strings, duplicate keys
  after normalization, non-mapping inputs, and invalid profile values.
- Default `heating` is an empty immutable mapping. Missing circuits remain
  unconfigured; supplying a None value is not a substitute for omitting a key.
- Capture defensive copies and freeze the collection and nested profiles. A
  frozen pydantic model containing an ordinary mutable dict is insufficient.
- `model_dump()` and JSON serialization must work; JSON roundtrips reconstruct
  the immutable integer-keyed collection without changing parameter ID strings.
  Standard `deepcopy()` and pydantic `model_copy(deep=True)` must still work.
- Reads and writes must use the same selected profile. Unsupported and missing
  circuits retain their existing error behavior; no fallback to another circuit.
- Remove numbered-field aliases rather than preserve parallel configuration.
- Update CLI construction/iteration, fixtures, examples, API/migration docs, and
  prior design/plan references so they all describe the same shape.
- Keep the existing worktree/PR and original checkout untouched. No live device
  access, release, new parameter IDs, or unrelated implementation changes.
- Run full tests with 95%+ total/100% patch coverage and all `prek` hooks.
