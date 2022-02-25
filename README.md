# Python: BSBLan API Client

[![GitHub Release][releases-shield]][releases]
![Project Stage][project-stage-shield]
![Project Maintenance][maintenance-shield]
[![License][license-shield]](LICENSE.md)

[![Build Status][build-shield]][build]
[![Code Coverage][codecov-shield]][codecov]
[![Code Quality][code-quality-shield]][code-quality]

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

from bsblan import BSBLan, Info, State


async def main(loop):
    """Show example on controlling your BSBLan device.

    Options:
    - passkey (http://url/"passkey"/) if your device is setup for passkey authentication
    - username and password if your device is setup for username/password authentication

    """
    async with BSBLan(
        host="10.0.1.60", passkey=None, username=None, password=None, loop=loop
    ) as bsblan:
        # get state from bsblan device
        state: State = await bsblan.state()
        print(state)

        # set temp thermostat
        await bsblan.thermostat(target_temperature=19.0)

        # set hvac_mode (0-3) (protection,auto,reduced,comfort)
        await bsblan.thermostat(hvac_mode=3)

        # get some generic info from the heater
        info: Info = await bsblan.info()
        print(info)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
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

This Python project is fully managed using the [Poetry][poetry] dependency manager. But also relies on the use of NodeJS for certain checks during development.

You need at least:

- Python 3.9+
- [Poetry][poetry-install]
- NodeJS 16+ (including NPM)

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

Copyright (c) 2022 WJ van Rootselaar

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
[build-shield]: https://github.com/liudger/python-bsblan/workflows/Continuous%20Integration/badge.svg
[build]: https://github.com/liudger/python-bsblan/actions
[buymeacoffee-shield]: https://www.buymeacoffee.com/assets/img/guidelines/download-assets-sm-2.svg
[buymeacoffee]: https://www.buymeacoffee.com/liudger
[code-quality-shield]: https://img.shields.io/lgtm/grade/python/g/liudger/python-bsblan.svg?logo=lgtm&logoWidth=18
[code-quality]: https://lgtm.com/projects/g/liudger/python-bsblan/context:python
[codecov-shield]: https://codecov.io/gh/liudger/python-bsblan/branch/Dev/graph/badge.svg?token=ypos87GGxv
[codecov]: https://codecov.io/gh/liudger/python-bsblan
[contributors]: https://github.com/liudger/python-bsblan/graphs/contributors
[frenck]: https://github.com/frenck
[keepchangelog]: http://keepachangelog.com/en/1.0.0/
[license-shield]: https://img.shields.io/github/license/liudger/python-bsblan.svg
[liudger]: https://github.com/liudger
[live-coding]: https://www.youtube.com/watch?v=6LHeoUS1R40
[maintenance-shield]: https://img.shields.io/maintenance/yes/2022.svg
[poetry]: https://python-poetry.org
[poetry-install]: https://python-poetry.org/docs/#installation
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-yellow.svg
[releases-shield]: https://img.shields.io/github/v/release/liudger/python-bsblan.svg
[releases]: https://github.com/liudger/python-bsblan/releases
[semver]: http://semver.org/spec/v2.0.0.html
