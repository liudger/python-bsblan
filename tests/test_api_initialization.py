"""Tests for API data initialization error handling."""
# pylint: disable=protected-access

from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import (
    API_DATA_NOT_INITIALIZED_ERROR_MSG,
    API_VERSION_ERROR_MSG,
    API_VERSIONS,
)
from bsblan.exceptions import BSBLANError


@pytest.mark.asyncio
async def test_initialize_api_data_no_api_version() -> None:
    """Test initializing API data with no API version set."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # API version is None by default
    with pytest.raises(BSBLANError, match=API_VERSION_ERROR_MSG):
        await bsblan._initialize_api_data()


@pytest.mark.asyncio
async def test_initialize_api_data_unexpected_none() -> None:
    """Test edge case where API data is still None after initialization."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set API version but simulate data being None after initialization
    bsblan._api_version = "v3"

    # Mock API_VERSIONS to return None for this specific test
    with (
        patch("bsblan.bsblan.API_VERSIONS", {"v3": None}),
        pytest.raises(BSBLANError, match=API_DATA_NOT_INITIALIZED_ERROR_MSG),
    ):
        await bsblan._initialize_api_data()


@pytest.mark.asyncio
async def test_request_no_session() -> None:
    """Test request method with no session initialized."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Session is None by default
    with pytest.raises(BSBLANError, match="Session not initialized"):
        await bsblan._request()


@pytest.mark.asyncio
async def test_api_data_initialized_from_versions(monkeypatch: Any) -> None:
    """Test that API data is initialized from API_VERSIONS when None (line 141)."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        client = BSBLAN(config, session=session)

        # Set up client with minimal state
        client._api_version = "v1"
        client._api_data = None  # This should be initialized

        # Mock request to avoid real network calls
        request_mock: AsyncMock = AsyncMock(return_value={})
        monkeypatch.setattr(client, "_request", request_mock)

        # Call _initialize_api_validator which should initialize _api_data
        await client._initialize_api_validator()

        # Verify API data was initialized (should be a copy, not the same object)
        assert client._api_data is not None
        # Verify it started with the same keys as API_VERSIONS["v1"]
        assert set(client._api_data.keys()) == set(API_VERSIONS["v1"].keys())
        # Note: Values will differ after validation since validator modifies the copy


@pytest.mark.asyncio
async def test_api_data_property_raises_without_version() -> None:
    """Test _initialize_api_data raises error when API version is None (line 368)."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        client = BSBLAN(config, session=session)

        # Set both to None
        client._api_version = None
        client._api_data = None

        # This should raise BSBLANError
        with pytest.raises(BSBLANError, match="API version not set"):
            await client._initialize_api_data()
