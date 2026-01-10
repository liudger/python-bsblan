"""Tests for low-level parameter access methods."""

from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, BSBLANError
from bsblan.constants import API_V3


@pytest.mark.asyncio
async def test_read_parameters_by_id(
    mock_bsblan: BSBLAN,
    monkeypatch: Any,
) -> None:
    """Test reading specific parameters by their IDs."""
    # Arrange: mock response with parameter data
    mock_response = {
        "8740": {
            "name": "Raumtemperatur 1",
            "value": "21.5",
            "unit": "°C",
            "desc": "",
            "dataType": 0,
        },
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
    result = await mock_bsblan.read_parameters(["8740", "8000"])

    # Assert
    assert len(result) == 2
    assert "8740" in result
    assert "8000" in result
    assert result["8740"].value == 21.5  # Converted to float
    assert result["8000"].value == 114  # ENUM type, converted to int
    request_mock.assert_awaited_once_with(params={"Parameter": "8740,8000"})


@pytest.mark.asyncio
async def test_read_parameters_empty_list() -> None:
    """Test that empty parameter list raises error."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        with pytest.raises(BSBLANError, match="No parameter IDs provided"):
            await bsblan.read_parameters([])


@pytest.mark.asyncio
async def test_read_parameters_filters_missing(
    mock_bsblan: BSBLAN,
    monkeypatch: Any,
) -> None:
    """Test that missing parameters are filtered from result."""
    # Arrange: response only has one of the requested parameters
    mock_response = {
        "8740": {
            "name": "Raumtemperatur 1",
            "value": "21.5",
            "unit": "°C",
            "desc": "",
            "dataType": 0,
        },
    }
    monkeypatch.setattr(mock_bsblan, "_request", AsyncMock(return_value=mock_response))

    # Act
    result = await mock_bsblan.read_parameters(["8740", "9999"])

    # Assert: only existing parameter returned
    assert len(result) == 1
    assert "8740" in result
    assert "9999" not in result


@pytest.mark.asyncio
async def test_read_parameters_filters_invalid_data(
    mock_bsblan: BSBLAN,
    monkeypatch: Any,
) -> None:
    """Test that parameters with invalid data are filtered."""
    # Arrange: response with invalid data
    mock_response = {
        "8740": {
            "name": "Raumtemperatur 1",
            "value": "21.5",
            "unit": "°C",
            "desc": "",
            "dataType": 0,
        },
        "8000": None,  # Invalid data
    }
    monkeypatch.setattr(mock_bsblan, "_request", AsyncMock(return_value=mock_response))

    # Act
    result = await mock_bsblan.read_parameters(["8740", "8000"])

    # Assert: only valid parameter returned
    assert len(result) == 1
    assert "8740" in result


@pytest.mark.asyncio
async def test_get_parameter_id_found(monkeypatch: Any) -> None:
    """Test looking up parameter ID by name."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Act
        param_id = bsblan.get_parameter_id("current_temperature")

        # Assert
        assert param_id == "8740"


@pytest.mark.asyncio
async def test_get_parameter_id_not_found(monkeypatch: Any) -> None:
    """Test looking up unknown parameter name returns None."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Act
        param_id = bsblan.get_parameter_id("nonexistent_parameter")

        # Assert
        assert param_id is None


@pytest.mark.asyncio
async def test_get_parameter_id_no_api_data() -> None:
    """Test looking up parameter when API data not initialized."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        # _api_data is None by default

        # Act
        param_id = bsblan.get_parameter_id("current_temperature")

        # Assert
        assert param_id is None


@pytest.mark.asyncio
async def test_get_parameter_ids(monkeypatch: Any) -> None:
    """Test looking up multiple parameter IDs by name."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        # Act
        result = bsblan.get_parameter_ids(
            [
                "current_temperature",
                "hvac_mode",
                "nonexistent_param",
            ]
        )

        # Assert: only found parameters returned
        assert len(result) == 2
        assert result["current_temperature"] == "8740"
        assert result["hvac_mode"] == "700"
        assert "nonexistent_param" not in result


@pytest.mark.asyncio
async def test_read_parameters_by_name(monkeypatch: Any) -> None:
    """Test reading parameters by their names."""
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
            "700": {
                "name": "Betriebsart",
                "value": "1",
                "unit": "",
                "desc": "Automatik",
                "dataType": 1,
            },
        }
        monkeypatch.setattr(bsblan, "_request", AsyncMock(return_value=mock_response))

        # Act
        result = await bsblan.read_parameters_by_name(
            [
                "current_temperature",
                "hvac_mode",
            ]
        )

        # Assert
        assert len(result) == 2
        assert "current_temperature" in result
        assert "hvac_mode" in result
        assert result["current_temperature"].value == 21.5


@pytest.mark.asyncio
async def test_read_parameters_by_name_empty_list(monkeypatch: Any) -> None:
    """Test that empty parameter name list raises error."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        with pytest.raises(BSBLANError, match="No parameter names provided"):
            await bsblan.read_parameters_by_name([])


@pytest.mark.asyncio
async def test_read_parameters_by_name_no_api_data() -> None:
    """Test error when API data not initialized."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        # _api_data is None by default

        with pytest.raises(BSBLANError, match="API data not initialized"):
            await bsblan.read_parameters_by_name(["current_temperature"])


@pytest.mark.asyncio
async def test_read_parameters_by_name_unknown_names(monkeypatch: Any) -> None:
    """Test error when no parameter names can be resolved."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        with pytest.raises(
            BSBLANError,
            match="Could not resolve any parameter names",
        ):
            await bsblan.read_parameters_by_name(["fake_param", "another_fake"])
