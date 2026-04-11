"""Tests for API data initialization error handling."""
# pylint: disable=protected-access

import aiohttp
import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import (
    API_VERSIONS,
)
from bsblan.exceptions import BSBLANError


@pytest.mark.asyncio
async def test_request_no_session() -> None:
    """Test request method with no session initialized."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Session is None by default
    with pytest.raises(BSBLANError, match="Session not initialized"):
        await bsblan._request()


@pytest.mark.asyncio
async def test_api_data_initialized_from_versions() -> None:
    """Test that API data is initialized via _setup_api_validator."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        client = BSBLAN(config, session=session)

        # Set up client with minimal state
        client._api_version = "v1"
        client._api_data = None  # This should be initialized

        # Call _setup_api_validator which should initialize _api_data
        await client._setup_api_validator()

        # Verify API data was initialized (should be a copy, not the same object)
        assert client._api_data is not None
        # Verify it started with the same keys as API_VERSIONS["v1"]
        assert set(client._api_data.keys()) == set(API_VERSIONS["v1"].keys())


@pytest.mark.asyncio
async def test_copy_api_config_raises_without_version() -> None:
    """Test _copy_api_config raises error when API version is None."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        client = BSBLAN(config, session=session)

        # Set both to None
        client._api_version = None
        client._api_data = None

        # This should raise BSBLANError
        with pytest.raises(BSBLANError, match="API version not set"):
            client._copy_api_config()
