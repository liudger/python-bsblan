"""Tests for custom sensor/parameter reading methods."""

from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, BSBLANError, EntityInfo
from bsblan.constants import API_V3


@pytest.mark.asyncio
async def test_read_parameter_by_id(
    mock_bsblan: BSBLAN,
    monkeypatch: Any,
) -> None:
    """Test reading a single parameter by its ID."""
    # Arrange: mock response with parameter data
    mock_response = {
        "8740": {
            "name": "Raumtemperatur 1",
            "value": "21.5",
            "unit": "°C",
            "desc": "",
            "dataType": 0,
        },
    }
    request_mock = AsyncMock(return_value=mock_response)
    monkeypatch.setattr(mock_bsblan, "_request", request_mock)

    # Act
    result = await mock_bsblan.read_parameter("8740")

    # Assert
    assert result is not None
    assert isinstance(result, EntityInfo)
    assert result.value == 21.5  # Converted to float
    assert result.unit == "°C"
    assert result.name == "Raumtemperatur 1"
    request_mock.assert_awaited_once_with(params={"Parameter": "8740"})


@pytest.mark.asyncio
async def test_read_parameter_not_found(
    mock_bsblan: BSBLAN,
    monkeypatch: Any,
) -> None:
    """Test that missing parameter returns None."""
    # Arrange: response without the requested parameter
    mock_response: dict[str, Any] = {}
    monkeypatch.setattr(mock_bsblan, "_request", AsyncMock(return_value=mock_response))

    # Act
    result = await mock_bsblan.read_parameter("9999")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_read_parameter_empty_id() -> None:
    """Test that empty parameter ID raises error."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        with pytest.raises(BSBLANError, match="Parameter ID cannot be empty"):
            await bsblan.read_parameter("")


@pytest.mark.asyncio
async def test_read_parameter_invalid_data(
    mock_bsblan: BSBLAN,
    monkeypatch: Any,
) -> None:
    """Test that parameter with invalid data returns None."""
    # Arrange: response with None value
    mock_response = {
        "8740": None,
    }
    monkeypatch.setattr(mock_bsblan, "_request", AsyncMock(return_value=mock_response))

    # Act
    result = await mock_bsblan.read_parameter("8740")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_read_parameter_enum_type(
    mock_bsblan: BSBLAN,
    monkeypatch: Any,
) -> None:
    """Test reading a parameter with ENUM data type."""
    # Arrange: mock response with ENUM parameter
    mock_response = {
        "8000": {
            "name": "Status Heizkreis 1",
            "value": "114",
            "unit": "",
            "desc": "Heating Comfort",
            "dataType": 1,
        },
    }
    request_mock = AsyncMock(return_value=mock_response)
    monkeypatch.setattr(mock_bsblan, "_request", request_mock)

    # Act
    result = await mock_bsblan.read_parameter("8000")

    # Assert
    assert result is not None
    assert result.value == 114  # ENUM type, converted to int
    assert result.desc == "Heating Comfort"
    assert result.data_type == 1


@pytest.mark.asyncio
async def test_read_parameter_by_name_found(monkeypatch: Any) -> None:
    """Test reading a single parameter by its name."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Mock response
        mock_response = {
            "8740": {
                "name": "Raumtemperatur 1",
                "value": "21.5",
                "unit": "°C",
                "desc": "",
                "dataType": 0,
            },
        }
        monkeypatch.setattr(bsblan, "_request", AsyncMock(return_value=mock_response))

        # Act
        result = await bsblan.read_parameter_by_name("current_temperature")

        # Assert
        assert result is not None
        assert isinstance(result, EntityInfo)
        assert result.value == 21.5
        assert result.unit == "°C"


@pytest.mark.asyncio
async def test_read_parameter_by_name_not_found(monkeypatch: Any) -> None:
    """Test reading parameter by unknown name raises error."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Act & Assert
        with pytest.raises(
            BSBLANError,
            match="Could not resolve any parameter names: nonexistent_param",
        ):
            await bsblan.read_parameter_by_name("nonexistent_param")


@pytest.mark.asyncio
async def test_read_parameter_by_name_empty_name() -> None:
    """Test that empty parameter name raises error."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        with pytest.raises(BSBLANError, match="Parameter name cannot be empty"):
            await bsblan.read_parameter_by_name("")


@pytest.mark.asyncio
async def test_read_parameter_by_name_no_api_data() -> None:
    """Test error when API data not initialized."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        # _api_data is None by default

        with pytest.raises(BSBLANError, match="API data not initialized"):
            await bsblan.read_parameter_by_name("current_temperature")


@pytest.mark.asyncio
async def test_read_parameter_by_name_not_in_device(monkeypatch: Any) -> None:
    """Test that parameter not found in device returns None."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Mock response without the requested parameter
        mock_response: dict[str, Any] = {}
        monkeypatch.setattr(bsblan, "_request", AsyncMock(return_value=mock_response))

        # Act
        result = await bsblan.read_parameter_by_name("current_temperature")

        # Assert
        assert result is None
