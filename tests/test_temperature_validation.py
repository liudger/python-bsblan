"""Tests for temperature validation error handling."""
# pylint: disable=protected-access

from typing import Any, cast
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import API_VERSIONS, TEMPERATURE_RANGE_ERROR_MSG, APIConfig
from bsblan.exceptions import BSBLANError, BSBLANInvalidParameterError
from bsblan.utility import APIValidator


@pytest.mark.asyncio
async def test_validate_target_temperature_no_range() -> None:
    """Test validating target temperature with temperature range not initialized."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Mock _initialize_temperature_range to do nothing (simulate failure)
    async def mock_init_temp_range() -> None:
        pass

    bsblan._initialize_temperature_range = mock_init_temp_range  # type: ignore[method-assign]

    # Temperature range is not initialized by default
    with pytest.raises(BSBLANError, match=TEMPERATURE_RANGE_ERROR_MSG):
        await bsblan._validate_target_temperature("22.0")


@pytest.mark.asyncio
async def test_validate_target_temperature_invalid_value() -> None:
    """Test validating target temperature with invalid (non-numeric) value."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Initialize temperature range
    bsblan._min_temp = 10.0
    bsblan._max_temp = 30.0

    # Test with non-numeric value
    with pytest.raises(BSBLANInvalidParameterError):
        await bsblan._validate_target_temperature("invalid")


@pytest.mark.asyncio
async def test_validate_target_temperature_out_of_range() -> None:
    """Test validating target temperature with value outside allowed range."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Initialize temperature range
    bsblan._min_temp = 10.0
    bsblan._max_temp = 30.0

    # Test with value below minimum
    with pytest.raises(BSBLANInvalidParameterError):
        await bsblan._validate_target_temperature("5.0")

    # Test with value above maximum
    with pytest.raises(BSBLANInvalidParameterError):
        await bsblan._validate_target_temperature("35.0")


@pytest.mark.asyncio
async def test_validate_target_temperature_valid() -> None:
    """Test validating target temperature with valid value."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Initialize temperature range
    bsblan._min_temp = 10.0
    bsblan._max_temp = 30.0

    # Test with valid value (should not raise exception)
    await bsblan._validate_target_temperature("22.0")


@pytest.mark.asyncio
async def test_temperature_range_min_temp_not_available(monkeypatch: Any) -> None:
    """Test warning when min_temp is not available from device (line 332)."""
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

        # Mock static_values to return data without min_temp
        static_values_mock = AsyncMock()
        static_values_mock.return_value.min_temp = None
        static_values_mock.return_value.max_temp = AsyncMock()
        static_values_mock.return_value.max_temp.value = "30"
        monkeypatch.setattr(client, "static_values", static_values_mock)

        # This should log a warning
        await client._initialize_temperature_range()

        # min_temp should remain None
        assert client._min_temp is None


@pytest.mark.asyncio
async def test_temperature_range_max_temp_not_available(monkeypatch: Any) -> None:
    """Test warning when max_temp is not available from device (line 337)."""
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

        # Mock static_values to return data without max_temp
        static_values_mock = AsyncMock()
        static_values_mock.return_value.min_temp = AsyncMock()
        static_values_mock.return_value.min_temp.value = "10"
        static_values_mock.return_value.max_temp = None
        monkeypatch.setattr(client, "static_values", static_values_mock)

        # This should log a warning
        await client._initialize_temperature_range()

        # max_temp should remain None
        assert client._max_temp is None


@pytest.mark.asyncio
async def test_temperature_range_static_values_error(monkeypatch: Any) -> None:
    """Test warning when static_values() raises an error (lines 332-337)."""
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

        # Mock static_values to raise an error
        static_values_mock = AsyncMock(side_effect=BSBLANError("Test error"))
        monkeypatch.setattr(client, "static_values", static_values_mock)

        # This should log a warning and not raise
        await client._initialize_temperature_range()

        # Both should remain None
        assert client._min_temp is None
        assert client._max_temp is None
