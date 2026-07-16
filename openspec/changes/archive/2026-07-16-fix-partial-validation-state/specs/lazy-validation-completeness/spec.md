## ADDED Requirements

### Requirement: Section validation covers every requested parameter

Before a lazy section read uses its configured parameters, the client SHALL
validate support for every parameter ID required by that read. A prior validation
of a different included subset SHALL NOT make unvalidated parameter IDs appear
validated. The client SHALL not repeat validation for IDs already covered unless
validation state is explicitly reset.

#### Scenario: Filtered section read followed by unfiltered read

- **WHEN** a section is first read with `include` selecting one parameter and a
  later read requests the complete section
- **THEN** the later read validates every configured parameter ID not checked by
  the first read before fetching the complete section

#### Scenario: Differently filtered section read

- **WHEN** a section is read with one included parameter and later read with a
  different included parameter
- **THEN** the second read validates the newly requested parameter ID
- **AND** it does not revalidate the parameter ID already covered by the first
  read

#### Scenario: Unsupported parameter discovered by a later read

- **WHEN** a later section read validates a previously uncovered parameter ID
  that the device does not support
- **THEN** the client removes that parameter from the active configuration
- **AND** subsequent reads do not request that unsupported parameter

### Requirement: Hot-water group validation covers every requested parameter

Before a hot-water group read uses its cached parameters, the client SHALL
validate and cache every parameter ID required by that read. A prior validation
of an included subset SHALL NOT make the group complete for other parameter IDs.

#### Scenario: Filtered hot-water read followed by complete group read

- **WHEN** a hot-water group is first read with `include` selecting a subset and
  later read without `include`
- **THEN** the later read validates and caches every remaining supported
  parameter ID in that group before it fetches group data

#### Scenario: Differently filtered hot-water read

- **WHEN** a hot-water group is read with one included parameter and later read
  with a different included parameter
- **THEN** the second read validates and caches the newly requested parameter ID
- **AND** it does not revalidate the parameter ID already covered by the first
  read

### Requirement: Empty include results do not complete validation

When an include filter selects no parameter IDs in a section or hot-water group,
the client SHALL NOT record that owner as complete or add parameter coverage.

#### Scenario: Later valid read after no-match include

- **WHEN** an include filter matches no parameters and a later request selects
  one or more valid parameters from the same section or hot-water group
- **THEN** the later request validates its selected parameter IDs normally
