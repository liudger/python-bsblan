---
name: feature-doc-updates
description: Ensure README and documentation are updated when adding features in python-bsblan. Use when implementing new behavior, parameters, API surface changes, or user-visible capabilities.
argument-hint: What feature was added and which files changed?
---

# Feature Documentation Updates

Use this skill after implementing a feature so user-facing documentation stays accurate.

## When To Use

Use this workflow when a change includes one or more of the following:
- New public method, model field, parameter, or behavior.
- Changed defaults, constraints, validation, or supported API versions.
- New examples, setup steps, or migration considerations.
- Any change that would alter how users call or understand the library.

## Inputs

Collect these inputs before writing docs:
- Feature summary in one sentence.
- Files changed in src and tests.
- Any new parameter IDs and names.
- Breaking changes or renamed fields.
- Example usage snippet (if applicable).

## Procedure

1. Classify feature impact.
- User-facing: update README and docs pages.
- Internal-only refactor with identical behavior: docs update is optional; add a short rationale in PR notes.

2. Determine documentation targets.
- Update README when install, quick start, supported behavior, or public API usage changes.
- Update docs under docs/ when API, constants, models, or behavior explanations changed.
- Update examples/ when new behavior benefits from a runnable example.

3. Apply documentation updates.
- README: adjust feature lists, capability notes, usage snippets, and compatibility statements.
- docs/: update the relevant page in docs/api or docs/getting-started to match the implementation.
- Keep terms, parameter names, and types identical to source code.

4. Validate consistency with code.
- Confirm names in docs match constants and model fields exactly.
- Confirm examples call real methods and use valid arguments.
- Confirm version notes align with constants version-gating logic.

5. Check deprecations and renames.
- If a public field/parameter is renamed, document migration guidance.
- Mention deprecation behavior and replacement names in docs where users will see it.

6. Run quality checks.
- Run project checks: uv run prek run --all-files
- If API/docs behavior changed, run tests to verify examples and described behavior are still valid.

7. Final completion check.
- README updated if user-visible behavior changed.
- Relevant docs pages updated if API or behavior changed.
- Any required examples updated.
- PR description includes a short Docs Updated section listing touched doc files.

## Decision Rules

- Update README is required when feature discovery or onboarding changes.
- Update docs pages is required when API shape or semantics change.
- If neither changed, explicitly state why docs were not updated.

## Output Format

When using this skill, produce:
1. Documentation Impact Summary.
2. Files updated (README, docs pages, examples).
3. Any follow-up docs work still needed.
4. Validation status for checks/tests.
