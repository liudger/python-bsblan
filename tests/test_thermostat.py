"""Tests for sending values to the BSBLAN device."""

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest
from aresponses import Response, ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig
from bsblan.constants import MULTI_PARAMETER_ERROR_MSG
from bsblan.exceptions import (
    BSBLANError,
    BSBLANInvalidParameterError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


@pytest.fixture
async def mock_bsblan() -> AsyncGenerator[BSBLAN, None]:
    """Fixture to create a mocked BSBLAN instance."""
    config = BSBLANConfig(host="example.com")
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(config, session=session)
        bsblan._firmware_version = "1.0.38-20200730234859"
        bsblan._api_version = "v3"
        bsblan._min_temp = 8.0
        bsblan._max_temp = 30.0
        bsblan._temperature_range_initialized = True
        yield bsblan


@pytest.fixture
async def mock_aresponses() -> AsyncGenerator[ResponsesMockServer, None]:
    """Fixture to mock aiohttp responses."""
    async with ResponsesMockServer() as server:
        # Mock response for /JQ
        server.add(
            "example.com",
            "/JQ",
            "POST",
            Response(
                text=json.dumps(
                    {"714.0": {"value": "8.0"}, "716.0": {"value": "30.0"}},
                ),
                content_type="application/json",
            ),
        )
        yield server


def create_response_handler(expected_data: dict[str, Any]) -> Response:
    """Create a response handler that checks the request data."""

    async def response_handler(request: aiohttp.web.Request) -> Response:
        """Check the request data."""
        assert request.method == "POST"
        assert request.host == "example.com"
        assert request.path_qs == "/JS"
        actual_data = json.loads(await request.text())

        for key, value in expected_data.items():
            assert key in actual_data, f"Expected key '{key}' not found in actual data"
            if key == "EnumValue":
                # Allow both string and integer representations
                assert str(actual_data[key]) == str(value)
            else:
                assert actual_data[key] == value, (
                    f"Mismatch for key '{key}': expected {value}, "
                    f"got {actual_data[key]}"
                )

        return Response(
            text=json.dumps({"status": "success"}),
            content_type="application/json",
        )

    return response_handler


@pytest.mark.asyncio
async def test_change_temperature(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test changing BSBLAN temperature."""
    expected_data = {
        "Parameter": "710",
        "Value": "20",
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.thermostat(target_temperature="20")


@pytest.mark.asyncio
async def test_change_hvac_mode(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test changing BSBLAN HVAC mode."""
    expected_data = {
        "Parameter": "700",
        "EnumValue": 1,  # 1 corresponds to "auto" mode
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.thermostat(hvac_mode="auto")


@pytest.mark.asyncio
async def test_invalid_temperature(mock_bsblan: BSBLAN) -> None:
    """Test setting an invalid temperature."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.thermostat(target_temperature="35")


@pytest.mark.asyncio
async def test_invalid_hvac_mode(mock_bsblan: BSBLAN) -> None:
    """Test setting an invalid HVAC mode."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.thermostat(hvac_mode="invalid_mode")


@pytest.mark.asyncio
async def test_no_parameters(mock_bsblan: BSBLAN) -> None:
    """Test calling thermostat without parameters."""
    with pytest.raises(BSBLANError) as exc_info:
        await mock_bsblan.thermostat()
    assert str(exc_info.value) == MULTI_PARAMETER_ERROR_MSG
