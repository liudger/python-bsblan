---
agent: agent
description: Review code changes for python-bsblan library
---

# Code Review Checklist

Review the changes against the python-bsblan coding standards.

## Checklist

### Code Quality
- [ ] Type hints on all functions
- [ ] Docstrings on public methods
- [ ] Line length under 88 characters
- [ ] Consistent parameter naming (snake_case)

### Testing
- [ ] Tests added for new functionality
- [ ] Test coverage 95%+ total
- [ ] Patch coverage 100%

### Patterns
- [ ] Uses `pydantic` `BaseModel` for validation and serialization
- [ ] Uses `aiohttp` for async HTTP
- [ ] Follows existing parameter naming conventions
- [ ] Error handling uses custom exceptions (`BSBLANError`, `BSBLANConnectionError`)

### Prek
- [ ] Ruff passes (linting + formatting)
- [ ] MyPy passes (type checking)
- [ ] Pylint passes (code analysis)
- [ ] Pytest passes (tests)

## Run Validation

```bash
uv run prek run --all-files
uv run pytest --cov=src/bsblan --cov-report=term-missing
```
