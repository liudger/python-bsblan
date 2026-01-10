"""Test hot water config and schedule methods."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig
from bsblan.constants import API_V3
from bsblan.exceptions import BSBLANError
from bsblan.models import HotWaterConfig, HotWaterSchedule
from bsblan.utility import APIValidator
from tests import load_fixture


@pytest.mark.asyncio
async def test_hot_water_config(
    monkeypatch: Any,
) -> None:
    """Test getting BSBLAN hot water configuration."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("hot_water")
        bsblan._api_validator = api_validator

        # Set up the hot water parameter cache
        hot_water_cache = {
            "1601": "eco_mode_selection",
            "1614": "nominal_setpoint_max",
            "1630": "dhw_charging_priority",
            "1640": "legionella_function",
            "1645": "legionella_setpoint",
            "1660": "dhw_circulation_pump_release",
            "1661": "dhw_circulation_pump_cycling",
            "1663": "dhw_circulation_setpoint",
        }
        bsblan.set_hot_water_cache(hot_water_cache)

        # Mark config group as validated to skip validation logic
        bsblan._validated_hot_water_groups.add("config")

        # Mock the request response
        fixture_data: dict[str, Any] = json.loads(load_fixture("hot_water_state.json"))

        def mock_request(**kwargs: Any) -> dict[str, Any]:
            param_string = kwargs.get("params", {}).get("Parameter", "")
            if param_string:
                requested_param_ids = param_string.split(",")
                result: dict[str, Any] = {
                    param_id: fixture_data[param_id]
                    for param_id in requested_param_ids
                    if param_id in fixture_data
                }
                return result
            return fixture_data

        request_mock = AsyncMock(side_effect=mock_request)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        hot_water_config: HotWaterConfig = await bsblan.hot_water_config()

        # Assertions
        assert isinstance(hot_water_config, HotWaterConfig)
        # Verify that some configuration fields are present
        assert hasattr(hot_water_config, "nominal_setpoint_max")

        # The request should be called once
        request_mock.assert_called_once()


@pytest.mark.asyncio
async def test_hot_water_config_no_params_error(
    monkeypatch: Any,
) -> None:
    """Test hot water config error when no parameters available."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Create a mock API validator that returns empty parameters
        mock_validator = MagicMock()
        mock_validator.get_section_params.return_value = {}
        bsblan._api_validator = mock_validator

        # Set empty cache - no config parameters available
        bsblan.set_hot_water_cache({})

        # Mark config group as already validated (so it skips validation)
        bsblan._validated_hot_water_groups.add("config")

        with pytest.raises(
            BSBLANError,
            match="No hot water configuration parameters available",
        ):
            await bsblan.hot_water_config()


@pytest.mark.asyncio
async def test_hot_water_schedule(
    monkeypatch: Any,
) -> None:
    """Test getting BSBLAN hot water schedule."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("hot_water")
        bsblan._api_validator = api_validator

        # Set up the hot water parameter cache with schedule parameters
        hot_water_cache = {
            "561": "dhw_time_program_monday",
            "562": "dhw_time_program_tuesday",
            "563": "dhw_time_program_wednesday",
            "564": "dhw_time_program_thursday",
            "565": "dhw_time_program_friday",
            "566": "dhw_time_program_saturday",
            "567": "dhw_time_program_sunday",
            "576": "dhw_time_program_standard_values",
        }
        bsblan.set_hot_water_cache(hot_water_cache)

        # Mark schedule group as validated to skip validation logic
        bsblan._validated_hot_water_groups.add("schedule")

        # Create mock fixture data for schedule parameters
        schedule_fixture_data = {
            "561": {
                "name": "DHW time program Monday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Monday",
                "dataType": 0,
            },
            "562": {
                "name": "DHW time program Tuesday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Tuesday",
                "dataType": 0,
            },
            "563": {
                "name": "DHW time program Wednesday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Wednesday",
                "dataType": 0,
            },
            "564": {
                "name": "DHW time program Thursday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Thursday",
                "dataType": 0,
            },
            "565": {
                "name": "DHW time program Friday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Friday",
                "dataType": 0,
            },
            "566": {
                "name": "DHW time program Saturday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Saturday",
                "dataType": 0,
            },
            "567": {
                "name": "DHW time program Sunday",
                "value": "06:00-22:00",
                "unit": "",
                "desc": "DHW time program Sunday",
                "dataType": 0,
            },
            "576": {
                "name": "DHW time program standard values",
                "value": "1",
                "unit": "",
                "desc": "DHW time program standard values",
                "dataType": 0,
            },
        }

        def mock_request(**kwargs: Any) -> dict[str, Any]:
            param_string = kwargs.get("params", {}).get("Parameter", "")
            if param_string:
                requested_param_ids = param_string.split(",")
                result: dict[str, Any] = {
                    param_id: schedule_fixture_data[param_id]
                    for param_id in requested_param_ids
                    if param_id in schedule_fixture_data
                }
                return result
            return schedule_fixture_data

        request_mock = AsyncMock(side_effect=mock_request)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        hot_water_schedule: HotWaterSchedule = await bsblan.hot_water_schedule()

        # Assertions
        assert isinstance(hot_water_schedule, HotWaterSchedule)
        # Verify that some schedule fields are present
        assert hasattr(hot_water_schedule, "dhw_time_program_monday")

        # The request should be called once
        request_mock.assert_called_once()


@pytest.mark.asyncio
async def test_hot_water_schedule_no_params_error(
    monkeypatch: Any,
) -> None:
    """Test hot water schedule error when no parameters available."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Create a mock API validator that returns empty parameters
        mock_validator = MagicMock()
        mock_validator.get_section_params.return_value = {}
        bsblan._api_validator = mock_validator

        # Set empty cache - no schedule parameters available
        bsblan.set_hot_water_cache({})

        # Mark schedule group as already validated (so it skips validation)
        bsblan._validated_hot_water_groups.add("schedule")

        with pytest.raises(
            BSBLANError,
            match="No hot water schedule parameters available",
        ):
            await bsblan.hot_water_schedule()


@pytest.mark.asyncio
async def test_hot_water_state_no_params_error(
    monkeypatch: Any,
) -> None:
    """Test hot water state error when no essential parameters available."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Create a mock API validator that returns empty parameters
        mock_validator = MagicMock()
        mock_validator.get_section_params.return_value = {}
        bsblan._api_validator = mock_validator

        # Set empty cache - no essential parameters available
        bsblan.set_hot_water_cache({})

        # Mark essential group as already validated (so it skips validation)
        bsblan._validated_hot_water_groups.add("essential")

        with pytest.raises(
            BSBLANError,
            match="No essential hot water parameters available",
        ):
            await bsblan.hot_water_state()


@pytest.mark.asyncio
async def test_granular_hot_water_validation(
    monkeypatch: Any,
) -> None:
    """Test granular hot water parameter group validation."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        bsblan._api_validator = api_validator

        # Mock the request to return valid hot water params
        fixture_data: dict[str, Any] = json.loads(load_fixture("hot_water_state.json"))

        def mock_request(**kwargs: Any) -> dict[str, Any]:
            param_string = kwargs.get("params", {}).get("Parameter", "")
            if param_string:
                requested_param_ids = param_string.split(",")
                result: dict[str, Any] = {
                    param_id: fixture_data[param_id]
                    for param_id in requested_param_ids
                    if param_id in fixture_data
                }
                return result
            return fixture_data

        request_mock = AsyncMock(side_effect=mock_request)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Initially no groups validated
        assert len(bsblan._validated_hot_water_groups) == 0

        # Call hot_water_state - should validate essential group only
        await bsblan.hot_water_state()

        # Essential group should be validated
        assert "essential" in bsblan._validated_hot_water_groups
        assert "config" not in bsblan._validated_hot_water_groups
        assert "schedule" not in bsblan._validated_hot_water_groups

        # Cache should have essential params only
        assert len(bsblan._hot_water_param_cache) > 0


@pytest.mark.asyncio
async def test_granular_validation_empty_params(
    monkeypatch: Any,
) -> None:
    """Test granular validation when no params match filter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        # Empty hot_water section in API data
        api_data = {**API_V3, "hot_water": {}}
        monkeypatch.setattr(bsblan, "_api_data", api_data)

        api_validator = APIValidator(api_data)
        bsblan._api_validator = api_validator

        # Validation should complete without error even with empty params
        await bsblan._ensure_hot_water_group_validated("essential", {"1600", "1610"})

        # Group should be marked as validated
        assert "essential" in bsblan._validated_hot_water_groups


@pytest.mark.asyncio
async def test_populate_hot_water_cache_no_validator() -> None:
    """Test cache population when no API validator exists."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Ensure no validator is set
    bsblan._api_validator = None  # type: ignore[assignment]

    # Should not raise an error, just return without doing anything
    bsblan._populate_hot_water_cache()

    # Cache should still be empty
    assert len(bsblan._hot_water_param_cache) == 0


@pytest.mark.asyncio
async def test_ensure_hot_water_group_validated_no_validator() -> None:
    """Test _ensure_hot_water_group_validated raises error without validator."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        # No validator set
        bsblan._api_validator = None  # type: ignore[assignment]

        with pytest.raises(BSBLANError, match="API validator not initialized"):
            await bsblan._ensure_hot_water_group_validated("essential", {"1600"})


@pytest.mark.asyncio
async def test_ensure_hot_water_group_validated_no_api_data() -> None:
    """Test _ensure_hot_water_group_validated raises error without api_data."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        # Set validator but no api_data
        bsblan._api_validator = MagicMock()
        bsblan._api_data = None

        with pytest.raises(BSBLANError, match="API data not initialized"):
            await bsblan._ensure_hot_water_group_validated("essential", {"1600"})


@pytest.mark.asyncio
async def test_ensure_section_validated_no_validator() -> None:
    """Test _ensure_section_validated raises error without validator."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        # No validator set
        bsblan._api_validator = None  # type: ignore[assignment]

        with pytest.raises(BSBLANError, match="API validator not initialized"):
            await bsblan._ensure_section_validated("heating")


@pytest.mark.asyncio
async def test_setup_api_validator_no_api_version() -> None:
    """Test _setup_api_validator raises error without API version."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        # No API version set
        bsblan._api_version = None

        with pytest.raises(BSBLANError, match="API version not set"):
            await bsblan._setup_api_validator()


@pytest.mark.asyncio
async def test_granular_validation_filters_missing_params(
    monkeypatch: Any,
) -> None:
    """Test granular validation filters out missing parameters from response."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        bsblan._api_validator = api_validator

        # Mock response that's missing param "1610"
        mock_response = {
            "1600": {"name": "Operating mode", "value": 1, "unit": "", "desc": "On"},
            # "1610" is missing from response
        }

        request_mock = AsyncMock(return_value=mock_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Run validation - should filter out missing param
        await bsblan._ensure_hot_water_group_validated("test_missing", {"1600", "1610"})

        # Only "1600" should be in cache (1610 was missing)
        assert "1600" in bsblan._hot_water_param_cache
        assert "1610" not in bsblan._hot_water_param_cache
        assert "test_missing" in bsblan._validated_hot_water_groups


@pytest.mark.asyncio
async def test_granular_validation_filters_invalid_params(
    monkeypatch: Any,
) -> None:
    """Test granular validation filters out invalid parameter values."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        bsblan._api_validator = api_validator

        # Mock response with invalid values
        mock_response = {
            "1600": {"name": "Operating mode", "value": 1, "unit": "", "desc": "On"},
            "1610": {"name": "Setpoint", "value": "---", "unit": "°C", "desc": "---"},
            "1620": {"name": "Release", "value": None, "unit": "", "desc": ""},
        }

        request_mock = AsyncMock(return_value=mock_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Run validation - should filter out invalid params
        await bsblan._ensure_hot_water_group_validated(
            "test_invalid", {"1600", "1610", "1620"}
        )

        # Only "1600" should be in cache (others had invalid values)
        assert "1600" in bsblan._hot_water_param_cache
        assert "1610" not in bsblan._hot_water_param_cache  # value was "---"
        assert "1620" not in bsblan._hot_water_param_cache  # value was None
        assert "test_invalid" in bsblan._validated_hot_water_groups


@pytest.mark.asyncio
async def test_ensure_hot_water_group_double_check_after_lock() -> None:
    """Test double-check locking in _ensure_hot_water_group_validated."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"
        bsblan._api_data = {"hot_water": {"1600": "operating_mode"}}  # type: ignore[assignment]
        bsblan._api_validator = APIValidator(bsblan._api_data)

        # Mock the request
        bsblan._request = AsyncMock(  # type: ignore[method-assign]
            return_value={"1600": {"value": "1", "unit": ""}}
        )

        # Create the lock first
        bsblan._hot_water_group_locks["essential"] = asyncio.Lock()

        # First call validates
        await bsblan._ensure_hot_water_group_validated("essential", {"1600"})
        assert "essential" in bsblan._validated_hot_water_groups

        # Second call should hit the fast path (before lock)
        bsblan._request.reset_mock()  # type: ignore[attr-defined]
        await bsblan._ensure_hot_water_group_validated("essential", {"1600"})
        bsblan._request.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ensure_hot_water_group_concurrent_double_check() -> None:
    """Test that concurrent hot water group validation doesn't duplicate."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._api_version = "v3"
        bsblan._api_data = {"hot_water": {"1600": "operating_mode"}}  # type: ignore[assignment]
        bsblan._api_validator = APIValidator(bsblan._api_data)

        request_count = 0
        request_started = asyncio.Event()

        async def slow_request(
            params: Any = None,  # noqa: ARG001
        ) -> dict[str, Any]:
            nonlocal request_count
            request_count += 1
            request_started.set()
            await asyncio.sleep(0.1)
            return {"1600": {"value": "1", "unit": ""}}

        bsblan._request = slow_request  # type: ignore[method-assign]

        # Start two concurrent validations
        task1 = asyncio.create_task(
            bsblan._ensure_hot_water_group_validated("essential", {"1600"})
        )
        await request_started.wait()
        task2 = asyncio.create_task(
            bsblan._ensure_hot_water_group_validated("essential", {"1600"})
        )

        await asyncio.gather(task1, task2)

        # Only one request should have been made
        assert request_count == 1
