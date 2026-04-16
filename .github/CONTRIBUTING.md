# Contributing to python-bsblan

When contributing to this repository, please first discuss the change you wish
to make via issue, email, or any other method with the owners of this repository
before making a change.

Please note we have a [code of conduct][coc], please follow it in all your
interactions with the project.

## Issues and feature requests

You've found a bug in the source code, a mistake in the documentation or maybe
you'd like a new feature? You can help us by submitting an issue to our
[GitHub Repository][github]. Before you create an issue, make sure you search
the archive, maybe your question was already answered.

Even better: You could submit a pull request with a fix / new feature!

## Development setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Clone the repository
git clone https://github.com/liudger/python-bsblan.git
cd python-bsblan

# Install dependencies (including dev dependencies)
uv sync --dev
```

## Coding standards

All contributions must follow these requirements:

- **Python 3.12+** — use modern Python features and type hints on all functions
- **Line length** — maximum 88 characters (enforced by Ruff)
- **Linting** — code must pass Ruff, ty, and Pylint checks
- **Formatting** — code is formatted with Ruff (based on Black style)
- **Naming** — use `snake_case` for all parameter names and follow existing
  patterns in the codebase
- **Docstrings** — required on all public methods

### Running quality checks

Before submitting a pull request, run all pre-commit hooks:

```bash
uv run prek run --all-files
```

This runs Ruff (linting + formatting), ty (type checking), and Pylint
(code analysis) in one command.

## Testing requirements

- **Test coverage** — maintain **95%+ total coverage**
- **Patch coverage** — all new or modified code must have **100% coverage**
  (CI will fail otherwise)
- **Framework** — tests use `pytest` with `pytest-asyncio`

Run the test suite:

```bash
uv run pytest --cov=src/bsblan --cov-report=term-missing
```

## Pull request process

1. Search our repository for open or closed [pull requests][prs] that relate
   to your submission. You don't want to duplicate effort.

2. Fork the repository and create your branch from `main`.

3. Make your changes, ensuring all coding standards and testing requirements
   above are met.

4. Run `uv run prek run --all-files` to verify all checks pass.

5. Submit your pull request with a clear description of the changes.

6. You may merge the pull request once you have the sign-off of the project
   maintainer, or if you do not have permission to do that, you may request
   the maintainer to merge it for you.

[github]: https://github.com/liudger/python-bsblan/issues
[prs]: https://github.com/liudger/python-bsblan/pulls
[coc]: https://github.com/liudger/python-bsblan/blob/main/.github/CODE_OF_CONDUCT.md
