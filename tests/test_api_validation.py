"""Tests for BSBLAN API validation methods."""

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access

import json
from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig, APIValidator
from bsblan.constants import (
    API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG,
    API_DATA_NOT_INITIALIZED_ERROR_MSG,
)
from bsblan.exceptions import BSBLANError


@pytest.mark.asyncio
async def test_validate_api_section_success(aresponses: ResponsesMockServer) -> None:
    """Test successful API section validation."""
    # Mock the response for parameter validation
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps(
                {
                    "device": {
                        "5870": {"name": "Device Parameter", "value": 123, "unit": "°C"},
                    }
                }
            ),
        ),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        
        # Initialize API validator and data
        bsblan._api_version = "v3"
        bsblan._api_data = {
            "device": {
                "parameters": {
                    "5870": {
                        "name": "Device Parameter",
                        "min": 0,
                        "max": 100,
                        "unit": "°C",
                    }
                }
            }
        }
        bsblan._api_validator = APIValidator(bsblan._api_data)
        
        # Test validation
        await bsblan._validate_api_section("device")
        
        # Verify validation status
        assert bsblan._api_validator.is_section_validated("device")


@pytest.mark.asyncio
async def test_validate_api_section_no_validator() -> None:
    """Test API section validation with no validator initialized."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        
        # Ensure validator is None
        bsblan._api_validator = None
        
        with pytest.raises(BSBLANError, match=API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG):
            await bsblan._validate_api_section("device")


@pytest.mark.asyncio
async def test_validate_api_section_no_api_data() -> None:
    """Test API section validation with no API data initialized."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        
        # Initialize validator but not API data
        bsblan._api_validator = APIValidator({})
        bsblan._api_data = None
        
        with pytest.raises(BSBLANError, match=API_DATA_NOT_INITIALIZED_ERROR_MSG):
            await bsblan._validate_api_section("device")


@pytest.mark.asyncio
async def test_validate_api_section_invalid_section() -> None:
    """Test API section validation with invalid section."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        
        # Initialize validator and API data without the requested section
        bsblan._api_validator = APIValidator({})
        bsblan._api_data = {"heating": {}}
        
        with pytest.raises(BSBLANError, match="Section 'invalid_section' not found in API data"):
            await bsblan._validate_api_section("invalid_section")


@pytest.mark.asyncio
async def test_validate_api_section_validation_error(aresponses: ResponsesMockServer) -> None:
    """Test API section validation with validation error."""
    # Mock the response for parameter validation
    aresponses.add(
        "example.com",
        "/JQ",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=json.dumps(
                {
                    "device": {
                        "5870": {"name": "Different Name", "value": 123, "unit": "°C"},
                    }
                }
            ),
        ),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        
        # Set up for test
        bsblan._api_version = "v3"
        bsblan._api_data = {
            "device": {
                "parameters": {
                    "5870": {
                        "name": "Device Parameter",
                        "min": 0,
                        "max": 100,
                        "unit": "°C",
                    }
                }
            }
        }
        
        # We need to use this method to handle the exception in validate_section
        original_validate = APIValidator.validate_section
        
        # Create an actual validator to use
        validator = APIValidator(bsblan._api_data)
        
        # Mock the validate_section method to raise an exception
        def mock_validate(self, section, response):
            raise BSBLANError("Validation error")
            
        APIValidator.validate_section = mock_validate
        
        try:
            # Apply the validator
            bsblan._api_validator = validator
            
            # Create an async mock for _extract_params_summary
            async def mock_extract_params(_):
                return {"string_par": "5870"}
                
            bsblan._extract_params_summary = mock_extract_params
            
            # Test validation - should catch exception and log warning
            await bsblan._validate_api_section("device")
            
            # Test passes if we get here without exception
            # Should be reset so section is not validated
            assert not validator.is_section_validated("device")
        finally:
            # Restore original validate_section method
            APIValidator.validate_section = original_validate