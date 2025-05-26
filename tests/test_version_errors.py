"""Tests for API version and firmware version error handling."""

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
    device = Device(name="Test Device", version="3.1.0", MAC="00:11:22:33:44:55", uptime=1000)
    
    # Mock device method to return our test device
    with patch.object(bsblan, "device", AsyncMock(return_value=device)):
        # Also mock _set_api_version to avoid any side effects
        with patch.object(bsblan, "_set_api_version"):
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