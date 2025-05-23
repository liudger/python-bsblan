"""Tests for BSBLAN API validation methods."""

from __future__ import annotations

import contextlib

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access
import json
from typing import TYPE_CHECKING, Any, NoReturn

import aiohttp
import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import (
    API_DATA_NOT_INITIALIZED_ERROR_MSG,
    API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG,
)
from bsblan.exceptions import BSBLANError
from bsblan.utility import APIValidator

if TYPE_CHECKING:
    from aresponses import ResponsesMockServer


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
                        "5870": {
                            "name": "Device Parameter",
                            "value": 123,
                            "unit": "°C",
                        },
                    }
                }
            ),
        ),
    )

    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)

        # Initialize API validator and data
        bsblan._api_version = "v3"
        api_data_device_section = {
            "5870": {
                "name": "Device Parameter",
                "min": 0,
                "max": 100,
                "unit": "°C",
            }
        }
        bsblan._api_data = {"device": api_data_device_section}  # type: ignore[assignment]
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
        bsblan._api_validator = None  # type: ignore[assignment]

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
        bsblan._api_data = {"heating": {}}  # type: ignore[assignment]

        with pytest.raises(
            BSBLANError, match="Section 'invalid_section' not found in API data"
        ):
            await bsblan._validate_api_section("invalid_section")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_validate_api_section_validation_error(
    aresponses: ResponsesMockServer,
) -> None:
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
        api_data_device_section_error = {
            "5870": {
                "name": "Device Parameter",
                "min": 0,
                "max": 100,
                "unit": "°C",
            }
        }
        bsblan._api_data = {"device": api_data_device_section_error}  # type: ignore[assignment]

        original_validate = APIValidator.validate_section
        # Initialize bsblan._api_validator with the full _api_data
        bsblan._api_validator = APIValidator(bsblan._api_data)

        def mock_validate(
            _self: APIValidator, _section: str, _response: dict[str, Any]
        ) -> NoReturn:
            error_message = "Validation error"
            raise BSBLANError(error_message)

        APIValidator.validate_section = mock_validate  # type: ignore[method-assign, assignment]

        try:
            # _api_validator is already set on bsblan
            async def mock_extract_params(*_args: Any) -> dict[str, Any]:
                # Not using the parameters
                return {"string_par": "5870", "list": ["Device Parameter"]}

            bsblan._extract_params_summary = mock_extract_params  # type: ignore[assignment, method-assign]
            # Handle the exception because we expect it
            with contextlib.suppress(BSBLANError):
                await bsblan._validate_api_section("device")

            assert not bsblan._api_validator.is_section_validated("device")
        finally:
            APIValidator.validate_section = original_validate  # type: ignore[method-assign]
