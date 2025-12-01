"""Tests for retrieving BSBLAN info Library."""

# file deepcode ignore W0212: this is a testfile

from typing import Any
from unittest.mock import MagicMock

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig, Info

from . import load_fixture


@pytest.mark.asyncio
async def test_info(aresponses: ResponsesMockServer, monkeypatch: Any) -> None:
    """Test getting BSBLAN device information."""
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=load_fixture("info.json"),
        ),
    )  # disable=duplicate-code
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        # set _api_version
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Mock _api_validator with device section params
        mock_validator = MagicMock()
        mock_validator.get_section_params.return_value = {
            "6224": "device_identification",
            "6225": "controller_family",
            "6226": "controller_variant",
        }
        object.__setattr__(bsblan, "_api_validator", mock_validator)

        info: Info = await bsblan.info()
        assert info
        assert info.controller_family.value == 211
        assert info.controller_variant.value == 127
        assert info.device_identification.value == "RVS21.831F/127"
