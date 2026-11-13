"""Raw schedule diagnostics remain possible without a weekday mapping."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig
from bsblan.exceptions import BSBLANScheduleMappingError

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer


@pytest.mark.parametrize("param", ["501", "521", "561"])
async def test_raw_schedule_parameter_diagnostics(
    aresponses: ResponsesMockServer, param: str
) -> None:
    """Generic raw reads retain text/metadata without asserting weekday roles."""
    text = "06:00-24:00 ##:##-##:## ##:##-##:##"
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            text=json.dumps(
                {
                    param: {
                        "name": "x",
                        "value": text,
                        "unit": "",
                        "desc": "",
                        "dataType": 9,
                        "error": 0,
                    },
                }
            )
        ),
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        raw = await client.read_parameters([param])
    assert raw[param].value == text
    assert raw[param].data_type == 9


async def test_schedule_mapping_is_not_required_for_climate_state(
    aresponses: ResponsesMockServer,
) -> None:
    """Failing a schedule read must not poison unrelated climate availability."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            text=json.dumps(
                {
                    "710": {
                        "name": "x",
                        "value": "21",
                        "unit": "°C",
                        "desc": "",
                        "dataType": 0,
                        "error": 0,
                    },
                }
            )
        ),
        repeat=2,
    )
    async with aiohttp.ClientSession() as session:
        client = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        client._supports_full_config = True
        await client._setup_api_validator()
        with pytest.raises(BSBLANScheduleMappingError):
            await client.heating_schedule()
        state = await client.state(include=["target_temperature"])
    assert state.target_temperature.value == 21
