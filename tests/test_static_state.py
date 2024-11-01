"""Tests for retrieving information from the BSBLAN device."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# file deepcode ignore W0212: this is a testfile

import json
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, StaticState
from bsblan.constants import API_V3
from bsblan.utility import APIValidator

from . import load_fixture


@pytest.mark.asyncio
async def test_sensor(monkeypatch: Any) -> None:
    """Test getting BSBLAN state."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(config=BSBLANConfig(host="example.com"), session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("staticValues")
        bsblan._api_validator = api_validator

        # Mock the request response
        request_mock = AsyncMock(
            return_value=json.loads(load_fixture("static_state.json")),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        static: StaticState = await bsblan.static_values()
        assert isinstance(static, StaticState)
        assert static.min_temp is not None
        assert static.min_temp.value == 8.0
        assert static.max_temp is not None
        assert static.max_temp.value == 20.0
