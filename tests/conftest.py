"""Fixtures for the BSBLAN tests."""

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig
from bsblan.constants import API_V3


@pytest.fixture
async def mock_bsblan(
    aresponses: ResponsesMockServer,
    monkeypatch: Any,
) -> AsyncGenerator[BSBLAN, Any]:
    """Fixture to create a mocked BSBLAN instance."""
    monkeypatch.setenv("BSBLAN_PASS", "your_password")
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps({"status": "ok"}),
        ),
    )
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)
        initialize_api_data_mock: AsyncMock = AsyncMock()
        # return the constant dictionary
        monkeypatch.setattr(bsblan, "_initialize_api_data", initialize_api_data_mock)
        request_mock: AsyncMock = AsyncMock(return_value={"status": "ok"})
        monkeypatch.setattr(bsblan, "_request", request_mock)
        yield bsblan
