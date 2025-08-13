"""Test edge cases in bsblan.py for 100% coverage."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig
from bsblan.exceptions import BSBLANConnectionError, BSBLANError


@pytest.mark.asyncio
async def test_initialize_api_data_edge_case() -> None:
    """Test _initialize_api_data when API data is None after version setting."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Force API version to be set but data to be None
    bsblan._api_version = "v3"
    bsblan._api_data = None

    # This should trigger the defensive check in _initialize_api_data
    api_data = await bsblan._initialize_api_data()
    assert api_data is not None


@pytest.mark.asyncio
async def test_validate_api_section_key_error(monkeypatch: Any) -> None:
    """Test validate_api_section when section is not found in API data."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        # Set up basic initialization
        bsblan._firmware_version = "1.0.38-20200730234859"
        bsblan._api_version = "v3"
        bsblan._api_data = {"other_section": {}}  # type: ignore[assignment]

        # Mock API validator
        mock_validator = MagicMock()
        mock_validator.is_section_validated.return_value = False
        bsblan._api_validator = mock_validator

        # Mock request to avoid network calls
        request_mock = AsyncMock(return_value={})
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # This should trigger the KeyError path
        with pytest.raises(
            BSBLANError,
            match="Section 'nonexistent' not found in API data",
        ):
            await bsblan._validate_api_section("nonexistent")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_client_response_error_path(monkeypatch: Any) -> None:
    """Test aiohttp.ClientError handling in _request."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        # Mock session.request to raise ClientError
        mock_response = MagicMock()
        mock_response.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientError("Connection failed")
        )
        mock_response.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(session, "request", MagicMock(return_value=mock_response))

        with pytest.raises(BSBLANConnectionError):
            await bsblan._request()


@pytest.mark.asyncio
async def test_value_error_path(monkeypatch: Any) -> None:
    """Test ValueError handling in _request."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        # Mock a successful response but with invalid JSON processing
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(session, "request", MagicMock(return_value=mock_response))

        with pytest.raises(BSBLANError, match="Invalid JSON"):
            await bsblan._request()


def test_bsblan_config_initialization_edge_cases() -> None:
    """Test edge cases in BSBLAN initialization."""
    # Test that we can create a BSBLAN instance without session
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Verify initial state
    assert bsblan.session is None
    assert bsblan._initialized is False
    assert len(bsblan._hot_water_param_cache) == 0
