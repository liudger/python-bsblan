"""Tests for BSBLAN initialization methods."""

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access

import json

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import (
    API_VERSION_ERROR_MSG,
)
from bsblan.exceptions import BSBLANError


@pytest.mark.asyncio
async def test_initialize_api_data_v1(aresponses: ResponsesMockServer) -> None:
    """Test initialization of API data with v1 version."""
    # Mock the device config endpoint for v1
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps(
                {
                    "Brötje": {
                        "5870": "Some Parameter",
                    }
                }
            ),
        ),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v1"

        await bsblan._initialize_api_data()

        # Verify API data was initialized
        assert bsblan._api_data is not None


@pytest.mark.asyncio
async def test_initialize_api_data_v3(aresponses: ResponsesMockServer) -> None:
    """Test initialization of API data with v3 version."""
    # Mock the device info endpoint for v3
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps(
                {
                    "knownDevices": {
                        "0": {
                            "device": "Test Device",
                            "family": "123",
                            "type": "456",
                            "var": "789",
                        }
                    }
                }
            ),
        ),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"

        await bsblan._initialize_api_data()

        # Verify API data was initialized
        assert bsblan._api_data is not None


@pytest.mark.asyncio
async def test_api_version_error() -> None:
    """Test error when API version is not set."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)

        # Force api_version to None to test error condition
        bsblan._api_version = None

        with pytest.raises(BSBLANError, match=API_VERSION_ERROR_MSG):
            await bsblan._initialize_api_data()
