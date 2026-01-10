# GitHub Copilot Instructions for python-bsblan

This repository contains the `python-bsblan` library, an asynchronous Python client for BSB-LAN devices (heating controllers).

## Project Overview

- **Language**: Python 3.12+
- **Type**: Async library using `aiohttp`
- **Purpose**: Communicate with BSB-LAN devices to read/write heating parameters
- **License**: MIT

## Code Quality Standards

### Required Before Committing

Always run these commands after making changes:

```bash
# Run all pre-commit hooks (ruff, mypy, pylint, pytest)
uv run pre-commit run --all-files
```

### Pre-commit Includes
- **Ruff**: Linting and formatting (88 char line limit)
- **MyPy**: Static type checking
- **Pylint**: Code analysis
- **Pytest**: Test execution with coverage

### Coverage Requirements
- Maintain **95%+ total test coverage**
- **Patch coverage must be 100%** - all new/modified code must be fully tested
- GitHub Actions will fail if patch coverage is below 100%
- Run coverage check: `uv run pytest --cov=src/bsblan --cov-report=term-missing`

## Project Structure

```
src/bsblan/
├── __init__.py          # Package exports
├── bsblan.py            # Main BSBLAN client class
├── constants.py         # Parameter IDs and mappings
├── models.py            # Dataclass models for API responses
├── utility.py           # Helper utilities
├── exceptions.py        # Custom exceptions
└── py.typed             # PEP-561 marker

tests/
├── conftest.py          # Pytest fixtures
├── fixtures/            # JSON test data
└── test_*.py            # Test files
```

## Parameter Naming Conventions

### BSB-LAN Parameters
Parameters are identified by numeric IDs and mapped to readable names in `constants.py`.

**Naming Rules:**
- Use `snake_case` for all parameter names
- Group related parameters with common prefixes
- Legionella-related parameters use `legionella_function_*` prefix:
  - `legionella_function_setpoint` (ID: 1645)
  - `legionella_function_periodicity` (ID: 1641)
  - `legionella_function_day` (ID: 1642)
  - `legionella_function_time` (ID: 1644)
  - `legionella_function_dwelling_time` (ID: 1646)
- DHW (Domestic Hot Water) parameters use `dhw_*` prefix

### Adding New Parameters

1. **Add to `constants.py`**:
   ```python
   BASE_HOT_WATER_PARAMS: Final[dict[str, str]] = {
       "1645": "legionella_function_setpoint",  # Parameter ID: name
   }
   ```

2. **Add to model in `models.py`**:
   ```python
   @dataclass
   class HotWaterConfig(DataClassORJSONMixin):
       legionella_function_setpoint: ParameterValue | None = None
   ```

3. **Update method in `bsblan.py`** if the parameter is settable:
   ```python
   async def set_hot_water(
       self,
       legionella_function_setpoint: float | None = None,
   ) -> None:
   ```

4. **Add tests in `tests/test_*.py`**

## Polling Categories

Parameters are organized into polling categories based on how frequently they change:

### Fast Poll (State - every update)
- Current temperatures
- HVAC action/state
- Pump states

### Slow Poll (Config - every 5 minutes)
- Operating modes
- Setpoints
- Legionella function settings
- Time programs

### Static (rarely changes)
- Device identification
- Min/max temperature limits

## Hot Water Parameter Groups

Hot water parameters are split into groups for granular lazy loading:

| Group | Params | Method | Use Case |
|-------|--------|--------|----------|
| essential | 5 | `hot_water_state()` | Frequent polling |
| config | 16 | `hot_water_config()` | Advanced settings |
| schedule | 8 | `hot_water_schedule()` | Time programs |

Defined in `constants.py`:
- `HOT_WATER_ESSENTIAL_PARAMS` - operating_mode, nominal_setpoint, etc.
- `HOT_WATER_CONFIG_PARAMS` - legionella settings, eco mode, etc.
- `HOT_WATER_SCHEDULE_PARAMS` - daily time programs

## Data Models

### Model Pattern
All models use `mashumaro` for JSON serialization:

```python
from dataclasses import dataclass
from mashumaro.mixins.orjson import DataClassORJSONMixin

@dataclass
class HotWaterConfig(DataClassORJSONMixin):
    """Hot water configuration parameters."""
    operating_mode: ParameterValue | None = None
    nominal_setpoint: ParameterValue | None = None
```

### ParameterValue Structure
Each parameter returns a `ParameterValue` with:
- `value`: The actual value
- `unit`: Unit of measurement
- `desc`: Human-readable description
- `dataType`: Data type information

## Async Patterns

### Client Usage
```python
async with BSBLAN(host="192.168.1.100") as client:
    state = await client.state()
    await client.set_hot_water(nominal_setpoint=55.0)
```

### Lazy Loading Architecture
The library uses lazy loading for optimal performance:
- **Initialization**: Only fetches firmware version (fast startup)
- **Section validation**: Deferred until section is first accessed
- **Hot water granular loading**: Each method validates only its param group
- **Race condition prevention**: Per-section/group asyncio locks

```python
# Initialize() is fast - only fetches firmware
await client.initialize()  # ~0.02s

# Section validated on first access
await client.state()  # Validates heating section on first call

# Hot water methods validate only their param groups:
await client.hot_water_state()    # 5 essential params only
await client.hot_water_config()   # 16 config params only
await client.hot_water_schedule() # 8 schedule params only
```

### Concurrency & Locking
The library uses asyncio locks to prevent race conditions during lazy loading:
- `_section_locks`: Per-section locks (heating, sensor, etc.)
- `_hot_water_group_locks`: Per-group locks (essential, config, schedule)

Double-checked locking pattern:
1. Fast path: Check if validated (no lock)
2. Acquire lock for specific section/group
3. Double-check after acquiring lock
4. Perform validation inside the lock

This prevents duplicate network requests when concurrent calls access the same section before validation completes.

### Error Handling
- Use `BSBLANError` for general errors
- Use `BSBLANConnectionError` for connection issues
- Always validate only one parameter is set per API call

## Testing Patterns

### Test Structure
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

### Fixtures Location
Test fixtures (JSON responses) are in `tests/fixtures/`

## Common Tasks

### Adding a New Settable Parameter

1. Add parameter ID mapping in `constants.py`
2. Add field to appropriate model in `models.py`
3. Add parameter to method signature in `bsblan.py`
4. Update docstring with parameter description
5. Add state preparation logic in `_prepare_*_state()` method
6. Add tests for the new parameter
7. Run `uv run pre-commit run --all-files`

### Renaming a Parameter

When renaming parameters for consistency:
1. Update `constants.py` - parameter mapping
2. Update `models.py` - dataclass field
3. Update `bsblan.py` - method parameters and state handling
4. Update `tests/` - all test files using the parameter
5. Update `examples/` - any example code
6. Run `uv run pre-commit run --all-files`

## API Versions

The library supports BSB-LAN API versions:
- **v1**: Original API
- **v3**: Extended API with additional parameters

Version-specific parameters are handled in `constants.py` with extension dictionaries.

## Don't Forget

- ✅ Run `uv run pre-commit run --all-files` after every change
- ✅ Maintain 95%+ test coverage
- ✅ Use type hints on all functions
- ✅ Add docstrings to public methods
- ✅ Keep line length under 88 characters
- ✅ Use consistent parameter naming (check existing patterns)
