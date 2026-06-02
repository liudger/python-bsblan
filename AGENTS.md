# Agent Instructions for python-bsblan

This file is the canonical AI agent guide for this repository.

## Scope

- Applies to the whole workspace.
- Prefer links to project docs instead of duplicating large policy text.

## Environment

- Python 3.12+
- uv for Python dependency management
- Node.js (used by formatting hooks)

Setup commands:

```bash
npm install
make setup
```

## Required Validation

Before finishing changes, run:

```bash
uv run prek run --all-files
```

Useful test commands:

```bash
uv run pytest
uv run pytest --cov=src/bsblan --cov-report=term-missing
uv run pytest --no-cov tests/test_file.py -k test_name
```

Quality gate expectations:

- Keep total coverage at 95%+.
- Keep patch coverage at 100% for modified lines.

## Code Map

- `src/bsblan/bsblan.py`: main async client (`BSBLAN`), request handling, lazy loading
- `src/bsblan/constants.py`: parameter IDs and name mappings
- `src/bsblan/models.py`: response models (`pydantic`) and set-param models (`dataclass`)
- `src/bsblan/utility.py`: helpers and API validation
- `src/bsblan/exceptions.py`: library exceptions
- `tests/conftest.py`: shared pytest fixtures (`mock_bsblan`)

## Project Conventions

- Use type hints on all functions.
- Keep line length <= 88 chars (Ruff).
- Response/state models use `pydantic.BaseModel`.
- Set-parameter payload models use `@dataclass`.
- Parameter names use `snake_case`.
- For set operations, send one `/JS` request per populated parameter.
- Treat API v3 as the supported baseline (do not reintroduce v1-only behavior).

Naming patterns to preserve:

- `legionella_function_*`
- `dhw_*`

## Parameter Change Workflow

When adding or renaming parameters:

1. Query real-device raw data with `examples/fetch_param.py`.
2. Update mappings in `src/bsblan/constants.py`.
3. Update response models in `src/bsblan/models.py`.
4. If settable, update set dataclass and client setter logic.
5. Add/adjust tests in `tests/`.
6. Run full validation (`uv run prek run --all-files`).

If raw responses are incomplete or `data_type` is unknown, prefer
`EntityInfo[str] | None` and avoid guessing numeric types.

## Common Pitfalls

- Partial pytest runs can fail coverage gates; use `--no-cov` for focused checks.
- Missing Node.js dependencies can break formatting hooks.
- Do not confuse comfort/protective/cooling bounds when selecting IDs.

## Source-of-Truth Docs

- Contribution and development process: `.github/CONTRIBUTING.md`
- User-facing usage and setup: `README.md`
- Developer docs index: `docs/index.md`
- Getting started examples: `docs/getting-started.md`
- API reference: `docs/api/client.md`

## Legacy Compatibility

- `.github/copilot-instructions.md` and `CLAUDE.md` should reference this file.
