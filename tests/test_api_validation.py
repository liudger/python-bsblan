"""Tests for BSBLAN API validation methods."""

from __future__ import annotations

import asyncio
import contextlib

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access
import json
from typing import TYPE_CHECKING, Any, NoReturn, cast
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import (
    API_DATA_NOT_INITIALIZED_ERROR_MSG,
    API_VALIDATOR_NOT_INITIALIZED_ERROR_MSG,
    API_VERSIONS,
    APIConfig,
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
            APIValidator.validate_section = original_validate


@pytest.mark.asyncio
async def test_validate_section_already_validated(monkeypatch: Any) -> None:
    """Test section validation returns None when already validated (line 160)."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        client = BSBLAN(config, session=session)

        client._api_version = "v1"
        # Deep copy to avoid modifying the shared constant
        source_config = API_VERSIONS["v1"]
        client._api_data = cast(
            "APIConfig",
            {
                section: cast("dict[str, str]", params).copy()
                for section, params in source_config.items()
            },
        )
        client._api_validator = APIValidator(client._api_data)

        # Mock request
        request_mock: AsyncMock = AsyncMock(
            return_value={"710": {"name": "Target", "value": "20", "unit": "°C"}}
        )
        monkeypatch.setattr(client, "_request", request_mock)

        # First validation should succeed
        response_data = await client._validate_api_section("heating")
        assert response_data is not None

        # Second call should return None (already validated)
        response_data = await client._validate_api_section("heating")
        assert response_data is None


@pytest.mark.asyncio
async def test_validation_error_resets_section(monkeypatch: Any) -> None:
    """Test that validation errors reset the section (line 212)."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        client = BSBLAN(config, session=session)

        client._api_version = "v1"
        # Copy each section dictionary to avoid modifying the shared constant
        source_config = API_VERSIONS["v1"]
        client._api_data = cast(
            "APIConfig",
            {
                section: cast("dict[str, str]", params).copy()
                for section, params in source_config.items()
            },
        )
        client._api_validator = APIValidator(client._api_data)

        # Mock request to raise an error
        request_mock: AsyncMock = AsyncMock(side_effect=BSBLANError("Test error"))
        monkeypatch.setattr(client, "_request", request_mock)

        # This should raise BSBLANError and reset validation
        with pytest.raises(BSBLANError, match="Test error"):
            await client._validate_api_section("heating")


@pytest.mark.asyncio
async def test_setup_api_validator_api_data_already_exists() -> None:
    """Test _setup_api_validator when _api_data already exists."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"

        # Pre-set api_data
        existing_data = {"heating": {"700": "operating_mode"}}
        bsblan._api_data = existing_data  # type: ignore[assignment]

        await bsblan._setup_api_validator()

        # _api_data should remain unchanged (not overwritten)
        assert bsblan._api_data is existing_data
        assert bsblan._api_validator is not None


@pytest.mark.asyncio
async def test_setup_api_validator_initializes_api_data() -> None:
    """Test _setup_api_validator initializes _api_data when None."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"

        # Ensure _api_data is None
        bsblan._api_data = None

        await bsblan._setup_api_validator()

        # _api_data should be initialized from API config
        assert bsblan._api_data is not None
        assert "heating" in bsblan._api_data
        assert bsblan._api_validator is not None


@pytest.mark.asyncio
async def test_ensure_section_validated_double_check_after_lock() -> None:
    """Test double-check locking in _ensure_section_validated."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"
        bsblan._api_data = {"heating": {"700": "operating_mode"}}  # type: ignore[assignment]
        bsblan._api_validator = APIValidator(bsblan._api_data)

        # Track validation calls
        validation_count = 0

        async def mock_validate(section: str) -> dict[str, Any]:
            nonlocal validation_count
            validation_count += 1
            # Mark section as validated
            bsblan._api_validator.validated_sections.add(section)
            return {}

        bsblan._validate_api_section = mock_validate  # type: ignore[method-assign]

        # Create the lock first
        bsblan._section_locks["heating"] = asyncio.Lock()

        # First call validates
        await bsblan._ensure_section_validated("heating")
        assert validation_count == 1

        # Second call should skip (fast path - no lock needed)
        await bsblan._ensure_section_validated("heating")
        assert validation_count == 1  # Still 1, not called again


@pytest.mark.asyncio
async def test_ensure_section_validated_concurrent_double_check() -> None:
    """Test that concurrent calls don't duplicate validation."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"
        bsblan._api_data = {"heating": {"700": "operating_mode"}}  # type: ignore[assignment]
        bsblan._api_validator = APIValidator(bsblan._api_data)

        validation_count = 0
        validation_started = asyncio.Event()

        async def slow_validate(section: str) -> dict[str, Any]:
            nonlocal validation_count
            validation_count += 1
            validation_started.set()
            # Simulate slow validation
            await asyncio.sleep(0.1)
            bsblan._api_validator.validated_sections.add(section)
            return {}

        bsblan._validate_api_section = slow_validate  # type: ignore[method-assign]

        # Start two concurrent validations
        task1 = asyncio.create_task(bsblan._ensure_section_validated("heating"))
        # Wait for first validation to start
        await validation_started.wait()
        task2 = asyncio.create_task(bsblan._ensure_section_validated("heating"))

        await asyncio.gather(task1, task2)

        # Only one validation should have occurred due to double-check locking
        assert validation_count == 1


@pytest.mark.asyncio
async def test_validate_api_section_hot_water_cache() -> None:
    """Test that hot_water section validation populates the cache."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"
        bsblan._api_data = {  # type: ignore[assignment]
            "heating": {},
            "sensor": {},
            "staticValues": {},
            "device": {},
            "hot_water": {"1600": "operating_mode", "1610": "nominal_setpoint"},
        }
        bsblan._api_validator = APIValidator(bsblan._api_data)

        # Mock the request
        bsblan._request = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "1600": {"value": "1", "unit": ""},
                "1610": {"value": "55", "unit": "°C"},
            }
        )

        # Validate hot_water section
        await bsblan._validate_api_section("hot_water")

        # Cache should be populated
        assert len(bsblan._hot_water_param_cache) > 0


@pytest.mark.asyncio
async def test_ensure_section_validated_heating_extracts_temp_unit() -> None:
    """Test that heating section validation extracts temperature unit."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"
        bsblan._api_data = {"heating": {"710": "target_temperature"}}  # type: ignore[assignment]
        bsblan._api_validator = APIValidator(bsblan._api_data)

        # Mock _validate_api_section to return response with temp unit
        async def mock_validate(section: str) -> dict[str, Any]:
            bsblan._api_validator.validated_sections.add(section)
            if section == "heating":
                return {"710": {"value": "20.0", "unit": "°F"}}
            return {}

        bsblan._validate_api_section = mock_validate  # type: ignore[method-assign]

        await bsblan._ensure_section_validated("heating")

        # Temperature unit should be extracted from heating response
        assert bsblan._temperature_unit == "°F"


@pytest.mark.asyncio
async def test_setup_api_validator_skips_api_data_init_when_exists() -> None:
    """Test that _setup_api_validator doesn't override existing _api_data."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"

        # Pre-set custom api_data
        custom_data: dict[str, Any] = {"heating": {"custom": "value"}}
        bsblan._api_data = custom_data  # type: ignore[assignment]

        # Track if _copy_api_config is called
        copy_called = False
        original_copy = bsblan._copy_api_config

        def mock_copy() -> Any:
            nonlocal copy_called
            copy_called = True
            return original_copy()

        bsblan._copy_api_config = mock_copy  # type: ignore[method-assign]

        await bsblan._setup_api_validator()

        # _copy_api_config should NOT be called since _api_data exists
        assert not copy_called
        # Original data should be preserved
        assert bsblan._api_data is custom_data
