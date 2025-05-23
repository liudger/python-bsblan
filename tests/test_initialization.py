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


@pytest.mark.asyncio
async def test_context_manager(aresponses: ResponsesMockServer) -> None:
    """Test the context manager functionality."""
    # Mock the API responses to enable a successful initialization
    aresponses.add(
        "example.com",
        "/JC",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps({"version": "1.0"}),
        ),
    )

    # Mock a simple success response for any remaining API calls
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps({"success": True}),
        ),
        repeat=True,
    )

    # Patch the initialize method
    original_initialize = BSBLAN.initialize
    try:

        async def mock_initialize(self: BSBLAN) -> None:
            self._initialized = True

        BSBLAN.initialize = mock_initialize  # type: ignore[method-assign]

        # Now test the context manager
        async with BSBLAN(BSBLANConfig(host="example.com")) as bsblan:
            assert bsblan.session is not None
            assert bsblan._close_session is True
    finally:
        # Restore the original method
        BSBLAN.initialize = original_initialize  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_initialize_with_session(aresponses: ResponsesMockServer) -> None:
    """Test initialize method with existing session."""
    # Mock responses
    aresponses.add(
        "example.com",
        "/JC",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps({"version": "1.0"}),
        ),
    )

    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps({"success": True}),
        ),
        repeat=True,
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)

        # Save original methods
        original_fetch_firmware = bsblan._fetch_firmware_version
        original_initialize_validator = bsblan._initialize_api_validator
        original_initialize_temp_range = bsblan._initialize_temperature_range
        original_initialize_api_data = bsblan._initialize_api_data

        try:
            # Replace with async mock functions
            async def mock_fetch_firmware() -> None:
                pass

            async def mock_initialize_validator() -> None:
                pass

            async def mock_initialize_temp_range() -> None:
                pass

            async def mock_initialize_api_data() -> None:
                pass

            bsblan._fetch_firmware_version = mock_fetch_firmware  # type: ignore[method-assign]
            bsblan._initialize_api_validator = mock_initialize_validator  # type: ignore[method-assign]
            bsblan._initialize_temperature_range = mock_initialize_temp_range  # type: ignore[method-assign]
            bsblan._initialize_api_data = mock_initialize_api_data  # type: ignore[method-assign, assignment]

            await bsblan.initialize()

            assert bsblan._initialized is True
            assert bsblan._close_session is False
        finally:
            # Restore original methods
            bsblan._fetch_firmware_version = original_fetch_firmware  # type: ignore[method-assign]
            bsblan._initialize_api_validator = original_initialize_validator  # type: ignore[method-assign]
            bsblan._initialize_temperature_range = original_initialize_temp_range  # type: ignore[method-assign]
            bsblan._initialize_api_data = original_initialize_api_data  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_initialize_api_validator() -> None:
    """Test initialize_api_validator method."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"
        bsblan._api_data = {
            "heating": {},
            "sensor": {},
            "staticValues": {},
            "device": {},
            "hot_water": {},
        }

        # Create a coroutine mock for _validate_api_section
        async def mock_validate_section(_section: str) -> None:
            pass

        bsblan._validate_api_section = mock_validate_section  # type: ignore[method-assign, assignment]

        await bsblan._initialize_api_validator()

        assert bsblan._api_validator is not None
