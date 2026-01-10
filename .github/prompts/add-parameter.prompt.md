---
agent: agent
description: Add a new BSB-LAN parameter to the library
---

# Add BSB-LAN Parameter

Add a new parameter to the python-bsblan library following the established patterns.

## Required Information

- Parameter ID (numeric, e.g., "1645")
- Parameter name (snake_case, e.g., "legionella_function_setpoint")
- Category: state (fast poll), config (slow poll), or static
- Is it settable? (yes/no)
- Data type (float, int, string, enum)

## Files to Modify

1. `src/bsblan/constants.py` - Add parameter ID mapping
2. `src/bsblan/models.py` - Add field to appropriate model
3. `src/bsblan/bsblan.py` - Add to setter method if settable
4. `tests/test_*.py` - Add tests for the new parameter

## Validation

After changes, run:
```bash
uv run pre-commit run --all-files
```

Coverage must be 95%+ total and 100% for new code.
