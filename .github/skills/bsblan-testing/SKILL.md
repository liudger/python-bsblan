---
name: bsblan-testing
description: Write and run tests for the python-bsblan library. Use this skill when creating unit tests, working with fixtures, or ensuring code coverage requirements are met.
---

# Testing python-bsblan

This skill guides you through testing practices for the python-bsblan library.

## Test Structure

Tests are located in `tests/` and use pytest with async support.

### Basic Test Pattern

```python
import pytest
from bsblan import BSBLAN

@pytest.mark.asyncio
async def test_feature_name(mock_bsblan: BSBLAN) -> None:
    """Test description."""
    # Arrange
    expected_value = "expected"

    # Act
    result = await mock_bsblan.some_method()

    # Assert
    assert result == expected_value
```

### Using Fixtures

Test fixtures (JSON responses) are in `tests/fixtures/`. Common fixtures:

- `device.json` - Device information
- `state.json` - Current state
- `hot_water_state.json` - Hot water state
- `sensor.json` - Sensor readings

Load fixtures using the `load_fixture` helper from `conftest.py`.

## Coverage Requirements

- **Total coverage**: 95%+ required
- **Patch coverage**: 100% required (all new/modified code must be tested)

Check coverage:

```bash
uv run pytest --cov=src/bsblan --cov-report=term-missing
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_bsblan.py

# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/test_bsblan.py::test_function_name
```

## Pre-commit Hooks

Always run before committing:

```bash
uv run pre-commit run --all-files
```

This runs:

- **Ruff**: Linting and formatting (88 char line limit)
- **MyPy**: Static type checking
- **Pylint**: Code analysis
- **Pytest**: Test execution with coverage

## Mock Patterns

For API calls, use `mock_bsblan` fixture and verify calls:

```python
mock_bsblan._request.assert_awaited_with(
    base_path="/JS",
    data={"Parameter": "1610", "Value": "60.0", "Type": "1"},
)
```

## Testing Lazy Loading

When testing hot water methods, mark param groups as validated to skip network calls:

```python
@pytest.mark.asyncio
async def test_hot_water_no_params_error(monkeypatch: Any) -> None:
    """Test error when no parameters available."""
    bsblan = BSBLAN(config, session=session)

    # Set empty cache and mark group as validated
    bsblan.set_hot_water_cache({})
    bsblan._validated_hot_water_groups.add("essential")  # Skip validation

    with pytest.raises(BSBLANError, match="No essential hot water"):
        await bsblan.hot_water_state()
```

For full integration tests with mocked responses:

```python
# Mark group as validated to use cached params
bsblan._validated_hot_water_groups.add("config")
bsblan.set_hot_water_cache({"1601": "eco_mode_selection", ...})
```

## Testing Concurrent Access

The library uses asyncio locks for race condition prevention. When testing:

- Locks are created per-section/group automatically
- Access `_section_locks` and `_hot_water_group_locks` dicts if needed
- The double-checked locking pattern prevents duplicate validations

```python
# Locks are stored in these dictionaries:
bsblan._section_locks  # {"heating": Lock(), "sensor": Lock(), ...}
bsblan._hot_water_group_locks  # {"essential": Lock(), ...}
```
