# python-bsblan

Asynchronous Python client for [BSB-LAN](https://github.com/fredlcore/bsb_lan) devices.

## Features

- Async/await support using `aiohttp`
- Read heating state, sensor data, and device information
- Control thermostat settings and hot water parameters
- Detect optional cooling setpoints for heat/cool range controls
- Fully typed with PEP 561 support
- API v3 parameter support
- Lazy loading with per-section validation

## Quick example

```python
import asyncio
from bsblan import BSBLAN, BSBLANConfig

async def main() -> None:
    config = BSBLANConfig(host="192.168.1.100")
    async with BSBLAN(config) as client:
        state = await client.state()
        print(f"Current temperature: {state.current_temperature.value}")

asyncio.run(main())
```

## Navigation

- [Getting Started](getting-started.md) — Installation, configuration, and usage
- [API Reference](api/client.md) — Full API documentation
