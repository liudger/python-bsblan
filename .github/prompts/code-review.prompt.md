---
name: Code Review
agent: agent
description: Review python-bsblan changes with findings first and repo quality gates
argument-hint: "Scope to review (staged changes, PR #, or file paths)"
---

# Code Review

Review the requested scope for regressions, correctness issues, and missing
tests.

Prioritize findings over summaries and order findings by severity.
Use this output format:

1. Findings
- Severity (`high`, `medium`, `low`), location, and impact.
- Include precise file references and actionable fixes.

2. Open Questions / Assumptions
- Unknowns that block confidence in the review.

3. Change Summary
- Brief recap only after findings.

Reference these standards while reviewing:
- [CONTRIBUTING](../CONTRIBUTING.md)
- [Copilot instructions](../copilot-instructions.md)

## Review Checks

### Code Quality
- [ ] Type hints on all functions
- [ ] Docstrings on public methods
- [ ] Line length under 88 characters
- [ ] Consistent parameter naming (snake_case)

### Testing
- [ ] Tests added for new functionality
- [ ] Total coverage remains 95%+
- [ ] Patch coverage for changed code is 100%

### Patterns
- [ ] Response models use `pydantic` `BaseModel`
- [ ] Set-parameter models use `@dataclass`
- [ ] Uses `aiohttp` for async HTTP
- [ ] Follows existing parameter naming conventions
- [ ] Error handling uses custom exceptions (`BSBLANError`,
	  `BSBLANConnectionError`)

### Prek
- [ ] Ruff passes (linting + formatting)
- [ ] ty passes (type checking)
- [ ] Pylint passes (code analysis)
- [ ] Pytest passes (tests)

## Validation Commands

```bash
uv run prek run --all-files
uv run pytest --cov=src/bsblan --cov-report=term-missing
```

If no findings are discovered, explicitly say so and list any residual testing
gaps.
