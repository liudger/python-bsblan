"""Tests for API version and firmware version error handling."""
# pylint: disable=protected-access

from unittest.mock import AsyncMock, patch

import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import API_VERSION_ERROR_MSG, FIRMWARE_VERSION_ERROR_MSG
from bsblan.exceptions import BSBLANError, BSBLANVersionError
from bsblan.models import Device


@pytest.mark.asyncio
async def test_set_api_version_without_firmware() -> None:
    """Test setting API version with firmware version not set."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Firmware version is None by default
    with pytest.raises(BSBLANError, match=FIRMWARE_VERSION_ERROR_MSG):
        bsblan._set_api_version()


@pytest.mark.asyncio
async def test_set_api_version_unsupported() -> None:
    """Test setting API version with unsupported firmware version."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to an unsupported value (between 1.2.0 and 3.0.0)
    bsblan._firmware_version = "2.0.0"

    with pytest.raises(BSBLANVersionError):
        bsblan._set_api_version()


@pytest.mark.asyncio
async def test_set_api_version_v1() -> None:
    """Test setting API version with v1 compatible firmware."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to v1 compatible
    bsblan._firmware_version = "1.0.0"
    bsblan._set_api_version()

    assert bsblan._api_version == "v1"


@pytest.mark.asyncio
async def test_set_api_version_v3() -> None:
    """Test setting API version with v3 compatible firmware."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to v3 compatible
    bsblan._firmware_version = "3.0.0"
    bsblan._set_api_version()

    assert bsblan._api_version == "v3"


@pytest.mark.asyncio
async def test_fetch_firmware_version() -> None:
    """Test fetching firmware version from device."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Create mock device with test version
    device = Device(
        name="Test Device", version="3.1.0", MAC="00:11:22:33:44:55", uptime=1000
    )

    # Mock device method to return our test device
    with (
        patch.object(bsblan, "device", AsyncMock(return_value=device)),
        patch.object(bsblan, "_set_api_version"),
    ):
        await bsblan._fetch_firmware_version()

        # Verify firmware version was set
        assert bsblan._firmware_version == "3.1.0"


@pytest.mark.asyncio
async def test_initialize_api_validator_no_api_version() -> None:
    """Test initialize API validator with no API version set."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # API version is None by default
    with pytest.raises(BSBLANError, match=API_VERSION_ERROR_MSG):
        await bsblan._initialize_api_validator()


@pytest.mark.asyncio
async def test_set_api_version_v5() -> None:
    """Test setting API version with v5 compatible firmware (BSB-LAN 5.x)."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to 5.0.16 (current BSB-LAN version)
    bsblan._firmware_version = "5.0.16"
    bsblan._set_api_version()

    assert bsblan._api_version == "v3"  # BSB-LAN 5.x uses v3 API with extensions


@pytest.mark.asyncio
async def test_set_api_version_v5_early() -> None:
    """Test setting API version with early v5 compatible firmware."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to 5.0.0 (first 5.x version)
    bsblan._firmware_version = "5.0.0"
    bsblan._set_api_version()

    assert bsblan._api_version == "v3"  # BSB-LAN 5.x uses v3 API with extensions


@pytest.mark.asyncio
async def test_process_response_v5_payload_removal() -> None:
    """Test that BSB-LAN 5.x payload field is removed from responses."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to 5.0.16
    bsblan._firmware_version = "5.0.16"

    # Mock response with payload field (as added in BSB-LAN 5.0+)
    response_with_payload = {
        "8700": {"value": "20.5", "unit": "°C"},
        "8740": {"value": "21.0", "unit": "°C"},
        "payload": "debug_payload_data_here",
    }

    # Process the response
    processed = bsblan._process_response(response_with_payload, "/JQ")

    # Payload should be removed
    expected = {
        "8700": {"value": "20.5", "unit": "°C"},
        "8740": {"value": "21.0", "unit": "°C"},
    }

    assert processed == expected
    assert "payload" not in processed


@pytest.mark.asyncio
async def test_process_response_non_jq_endpoint() -> None:
    """Test that non-JQ endpoints are not processed for payload removal."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to 5.0.16
    bsblan._firmware_version = "5.0.16"

    # Mock response with payload field
    response_with_payload = {
        "name": "BSB-LAN",
        "version": "5.0.16",
        "payload": "should_remain_for_non_jq",
    }

    # Process the response for non-JQ endpoint
    processed = bsblan._process_response(response_with_payload, "/JI")

    # Payload should remain for non-JQ endpoints
    assert processed == response_with_payload
    assert "payload" in processed


@pytest.mark.asyncio
async def test_set_api_version_v5_edge_cases() -> None:
    """Test edge cases for BSB-LAN 5.x version detection."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Test version 4.9.9 (should still be v3, not v5)
    bsblan._firmware_version = "4.9.9"
    bsblan._set_api_version()
    assert bsblan._api_version == "v3"

    # Test version 5.0.0-beta (should be v3)
    bsblan._firmware_version = "5.0.0"
    bsblan._set_api_version()
    assert bsblan._api_version == "v3"


@pytest.mark.asyncio
async def test_unsupported_version_still_fails() -> None:
    """Test that unsupported versions between 1.2.0 and 3.0.0 still fail."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Test that version 2.0.0 still fails (gap between v1 and v3)
    bsblan._firmware_version = "2.0.0"

    with pytest.raises(BSBLANVersionError):
        bsblan._set_api_version()
