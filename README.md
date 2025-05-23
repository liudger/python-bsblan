# Python: BSBLan API Client

[![GitHub Release][releases-shield]][releases]
[![Python Versions][python-versions-shield]][pypi]
![Project Stage][project-stage-shield]
![Project Maintenance][maintenance-shield]
[![License][license-shield]](.github/LICENSE.md)

[![Build Status][build-shield]][build]
[![Code Coverage][codecov-shield]][codecov]
[![Quality Gate Status][sonarcloud-shield]][sonarcloud]

[![Buy me a coffee][buymeacoffee-shield]][buymeacoffee]

Asynchronous Python client for BSBLan.

## About

This package allows you to control and monitor an BSBLan device
programmatically. It is mainly created to allow third-party programs to automate
the behavior of [BSBLan][bsblanmodule].

## Installation

```bash
pip install python-bsblan
```

## Usage

```python
# pylint: disable=W0621
"""Asynchronous Python client for BSBLan."""

import asyncio
import os

from bsblan import BSBLAN, BSBLANConfig, Device, Info, Sensor, State, StaticState


async def print_state(state: State) -> None:
    """Print the current state of the BSBLan device."""
    print(f"HVAC Action: {state.hvac_action.desc}")
    print(f"HVAC Mode: {state.hvac_mode.desc}")
    print(f"Current Temperature: {state.current_temperature.value}")


async def print_sensor(sensor: Sensor) -> None:
    """Print sensor information from the BSBLan device."""
    print(f"Outside Temperature: {sensor.outside_temperature.value}")


async def print_device_info(device: Device, info: Info) -> None:
    """Print device and general information."""
    print(f"Device Name: {device.name}")
    print(f"Version: {device.version}")
    print(f"Device Identification: {info.device_identification.value}")


async def print_static_state(static_state: StaticState) -> None:
    """Print static state information."""
    print(f"Min Temperature: {static_state.min_temp.value}")
    print(f"Max Temperature: {static_state.max_temp.value}")


async def main() -> None:
    """Show example on controlling your BSBLan device.

    Options:
    - passkey (http://url/"passkey"/) if your device is setup for passkey authentication
    - username and password if your device is setup for username/password authentication

    """
    # Create a configuration object
    config = BSBLANConfig(
        host="10.0.2.60",
        passkey=None,
        username=os.getenv("USERNAME"),  # Compliant
        password=os.getenv("PASSWORD"),  # Compliant
    )

    # Initialize BSBLAN with the configuration object
    async with BSBLAN(config) as bsblan:
        # Get and print state
        state: State = await bsblan.state()
        await print_state(state)

        # Set thermostat temperature
        print("\nSetting temperature to 18°C")
        await bsblan.thermostat(target_temperature="18")

        # Set HVAC mode
        print("Setting HVAC mode to heat")
        await bsblan.thermostat(hvac_mode="heat")

        # Get and print sensor information
        sensor: Sensor = await bsblan.sensor()
        await print_sensor(sensor)

        # Get and print device and general info
        device: Device = await bsblan.device()
        info: Info = await bsblan.info()
        await print_device_info(device, info)

        # Get and print static state
        static_state: StaticState = await bsblan.static_values()
        await print_static_state(static_state)


if __name__ == "__main__":
    asyncio.run(main())
```

## Changelog & Releases

This repository keeps a change log using [GitHub's releases][releases]
functionality. The format of the log is based on
[Keep a Changelog][keepchangelog].

Releases are based on [Semantic Versioning][semver], and use the format
of `MAJOR.MINOR.PATCH`. In a nutshell, the version will be incremented
based on the following:

- `MAJOR`: Incompatible or major changes.
- `MINOR`: Backwards-compatible new features and enhancements.
- `PATCH`: Backwards-compatible bugfixes and package updates.

## Contributing

This is an active open-source project. We are always open to people who want to
use the code or contribute to it.

We've set up a separate document for our
[contribution guidelines](CONTRIBUTING.md).

Thank you for being involved! :heart_eyes:

## Setting up development environment

This Python project is fully managed using the [Poetry][poetry] dependency manager.
But also relies on the use of NodeJS for certain checks during development.

You need at least:

- Python 3.12+
- [Poetry][poetry-install]
- NodeJS 22.14.0+ (including NPM)

To install all packages, including all development requirements:

```bash
npm install
poetry install
```

As this repository uses the [pre-commit][pre-commit] framework, all changes
are linted and tested with each commit. You can run all checks and tests
manually, using the following command:

```bash
poetry run pre-commit run --all-files
```

To run just the Python tests:

```bash
poetry run pytest
```

## Authors & contributors

The template is from the repository 'elgato' by [Franck Nijhof][frenck].
The setup of this repository is by [Willem-Jan van Rootselaar][liudger].

For a full list of all authors and contributors,
check [the contributor's page][contributors].

## License

MIT License

Copyright (c) 2023-2025 WJ van Rootselaar

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

[bsblanmodule]: https://github.com/fredlcore/bsb_lan
[build-shield]: https://github.com/liudger/python-bsblan/actions/workflows/tests.yaml/badge.svg
[build]: https://github.com/liudger/python-bsblan/actions
[buymeacoffee-shield]: https://www.buymeacoffee.com/assets/img/guidelines/download-assets-sm-2.svg
[buymeacoffee]: https://www.buymeacoffee.com/liudger
[codecov-shield]: https://codecov.io/gh/liudger/python-bsblan/branch/main/graph/badge.svg?token=ypos87GGxv
[codecov]: https://codecov.io/gh/liudger/python-bsblan
[contributors]: https://github.com/liudger/python-bsblan/graphs/contributors
[frenck]: https://github.com/frenck
[keepchangelog]: http://keepachangelog.com/en/1.0.0/
[license-shield]: https://img.shields.io/badge/license-MIT-blue.svg
[liudger]: https://github.com/liudger
[maintenance-shield]: https://img.shields.io/maintenance/yes/2025.svg
[poetry]: https://python-poetry.org
[poetry-install]: https://python-poetry.org/docs/#installation
[pre-commit]: https://pre-commit.com/
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-yellow.svg
[pypi]: https://pypi.org/project/python-bsblan/
[python-versions-shield]: https://img.shields.io/pypi/pyversions/python-bsblan
[releases-shield]: https://img.shields.io/github/v/release/liudger/python-bsblan.svg
[releases]: https://github.com/liudger/python-bsblan/releases
[semver]: http://semver.org/spec/v2.0.0.html
[sonarcloud-shield]: https://sonarcloud.io/api/project_badges/measure?project=liudger_python-bsblan&metric=alert_status
[sonarcloud]: https://sonarcloud.io/summary/new_code?id=liudger_python-bsblan
