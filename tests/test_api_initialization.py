"""Tests for API data initialization error handling."""
# pylint: disable=protected-access

from unittest.mock import patch

import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import API_DATA_NOT_INITIALIZED_ERROR_MSG, API_VERSION_ERROR_MSG
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
