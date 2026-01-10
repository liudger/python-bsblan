---
name: bsblan-parameters
description: Add new BSB-LAN parameters to the python-bsblan library. Use this skill when adding parameter IDs, updating models, or extending the API to support new heating controller parameters.
---

# Adding BSB-LAN Parameters

This skill guides you through adding new parameters to the python-bsblan library.

## Parameter Naming Conventions

- Use `snake_case` for all parameter names
- Group related parameters with common prefixes
- Legionella-related parameters use `legionella_function_*` prefix
- DHW (Domestic Hot Water) parameters use `dhw_*` prefix

## Steps to Add a New Parameter

### 1. Add to `constants.py`

Add the parameter ID mapping:

```python
BASE_HOT_WATER_PARAMS: Final[dict[str, str]] = {
    "1645": "legionella_function_setpoint",  # Parameter ID: name
}
```

### 2. Add to Model in `models.py`

Add the field to the appropriate dataclass:

```python
@dataclass
class HotWaterConfig(DataClassORJSONMixin):
    legionella_function_setpoint: ParameterValue | None = None
```

### 3. Update Method in `bsblan.py` (if settable)

Add parameter to the method signature:

```python
async def set_hot_water(
    self,
    legionella_function_setpoint: float | None = None,
) -> None:
```

### 4. Add Tests

Create tests in `tests/test_*.py`:

```python
@pytest.mark.asyncio
async def test_set_hot_water(mock_bsblan: BSBLAN) -> None:
    """Test setting BSBLAN hot water state."""
    await mock_bsblan.set_hot_water(nominal_setpoint=60.0)
    mock_bsblan._request.assert_awaited_with(
        base_path="/JS",
        data={"Parameter": "1610", "Value": "60.0", "Type": "1"},
    )
```

## Polling Categories

Parameters are organized by update frequency:

- **Fast Poll (State)**: Current temperatures, HVAC action/state, pump states
- **Slow Poll (Config)**: Operating modes, setpoints, legionella settings, time programs
- **Static**: Device identification, min/max temperature limits

## Hot Water Parameter Groups

Hot water parameters use granular lazy loading. When adding a new hot water param, add it to the appropriate group in `constants.py`:

| Group                | Constant                      | Method                 |
| -------------------- | ----------------------------- | ---------------------- |
| Essential (5 params) | `HOT_WATER_ESSENTIAL_PARAMS`  | `hot_water_state()`    |
| Config (16 params)   | `HOT_WATER_CONFIG_PARAMS`     | `hot_water_config()`   |
| Schedule (8 params)  | `HOT_WATER_SCHEDULE_PARAMS`   | `hot_water_schedule()` |

```python
# In constants.py - add to appropriate group set:
HOT_WATER_ESSENTIAL_PARAMS: Final[set[str]] = {"1600", "1610", ...}
HOT_WATER_CONFIG_PARAMS: Final[set[str]] = {"1601", "1614", ...}
```

## Concurrency Safety

The library uses asyncio locks to prevent race conditions:

- `_section_locks`: Per-section locks for lazy loading
- `_hot_water_group_locks`: Per-group locks for hot water validation

When adding new sections or groups, the lock is created automatically on first access.

## Validation

Always run after changes:

```bash
uv run pre-commit run --all-files
uv run pytest --cov=src/bsblan --cov-report=term-missing
```

**Coverage requirements**: 95%+ total, 100% patch coverage.
