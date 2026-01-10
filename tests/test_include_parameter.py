"""Tests for the include parameter in fetch methods."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=too-many-arguments

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, State, StaticState
from bsblan.constants import (
    API_V3,
    EMPTY_INCLUDE_LIST_ERROR_MSG,
    INVALID_INCLUDE_PARAMS_ERROR_MSG,
)
from bsblan.exceptions import BSBLANError
from bsblan.utility import APIValidator

from . import load_fixture

# ========== Parametrized tests for section-based methods ==========


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "section", "test_params"),
    [
        ("state", "heating", {"include": "hvac_mode", "param_id": "700"}),
        ("sensor", "sensor", {"include": "outside_temperature", "param_id": "8700"}),
        ("info", "device", {"include": "device_identification", "param_id": "6224"}),
    ],
    ids=["state", "sensor", "info"],
)
async def test_section_method_with_include_single_param(
    monkeypatch: Any,
    method_name: str,
    section: str,
    test_params: dict[str, str],
) -> None:
    """Test section methods with a single parameter in include list."""
    include_param = test_params["include"]
    param_id = test_params["param_id"]

    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add(section)
        bsblan._api_validator = api_validator

        # Load appropriate fixture based on method
        fixture_map = {
            "state": "state.json",
            "sensor": "sensor.json",
            "info": "info.json",
        }
        fixture_data = json.loads(load_fixture(fixture_map[method_name]))
        partial_response = {param_id: fixture_data[param_id]}

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Get the method and call it
        method = getattr(bsblan, method_name)
        result = await method(include=[include_param])

        # Verify correct parameter was requested
        request_mock.assert_awaited_once()
        call_args = request_mock.call_args
        assert call_args.kwargs["params"]["Parameter"] == param_id

        # Verify the attribute is populated
        assert getattr(result, include_param) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "section"),
    [
        ("state", "heating"),
        ("sensor", "sensor"),
        ("static_values", "staticValues"),
        ("info", "device"),
    ],
    ids=["state", "sensor", "static_values", "info"],
)
async def test_section_method_with_empty_include_list(
    monkeypatch: Any,
    method_name: str,
    section: str,
) -> None:
    """Test section methods with empty include list raises specific error."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add(section)
        bsblan._api_validator = api_validator

        request_mock: AsyncMock = AsyncMock()
        monkeypatch.setattr(bsblan, "_request", request_mock)

        method = getattr(bsblan, method_name)
        with pytest.raises(BSBLANError) as exc_info:
            await method(include=[])

        assert str(exc_info.value) == EMPTY_INCLUDE_LIST_ERROR_MSG
        request_mock.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "section"),
    [
        ("state", "heating"),
        ("sensor", "sensor"),
        ("static_values", "staticValues"),
        ("info", "device"),
    ],
    ids=["state", "sensor", "static_values", "info"],
)
async def test_section_method_with_invalid_params(
    monkeypatch: Any,
    method_name: str,
    section: str,
) -> None:
    """Test section methods with all invalid parameters raises error."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add(section)
        bsblan._api_validator = api_validator

        request_mock: AsyncMock = AsyncMock()
        monkeypatch.setattr(bsblan, "_request", request_mock)

        method = getattr(bsblan, method_name)
        with pytest.raises(BSBLANError) as exc_info:
            await method(include=["nonexistent_param"])

        assert str(exc_info.value) == INVALID_INCLUDE_PARAMS_ERROR_MSG
        request_mock.assert_not_awaited()


# ========== Tests for _validate_api_section with include parameter ==========


@pytest.mark.asyncio
async def test_validate_api_section_with_include_filter(monkeypatch: Any) -> None:
    """Test _validate_api_section filters params when include is specified."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")

        # Set up API data with multiple params
        api_data = {
            "heating": {
                "700": "hvac_mode",
                "710": "target_temperature",
                "8740": "current_temperature",
            },
            "sensor": {},
            "staticValues": {},
            "device": {},
            "hot_water": {},
        }
        bsblan._api_data = api_data  # type: ignore[assignment]

        api_validator = APIValidator(api_data)
        bsblan._api_validator = api_validator

        # Mock request to return only the filtered param
        request_mock = AsyncMock(
            return_value={"700": {"value": "1", "unit": "", "desc": "Auto"}}
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        # Validate with include filter - should only request hvac_mode
        result = await bsblan._validate_api_section("heating", include=["hvac_mode"])

        # Verify only filtered param was requested
        request_mock.assert_awaited_once()
        call_args = request_mock.call_args
        assert call_args.kwargs["params"]["Parameter"] == "700"

        # Result should contain the response data
        assert result is not None
        assert "700" in result


@pytest.mark.asyncio
async def test_validate_section_skips_params_not_in_include() -> None:
    """Test validate_section skips params not in include list."""
    # Set up API config with multiple params
    api_config = {
        "heating": {
            "700": "hvac_mode",
            "710": "target_temperature",
            "8740": "current_temperature",
        },
    }

    api_validator = APIValidator(api_config)

    # Mock request data with only one param (simulating filtered response)
    request_data = {"700": {"value": "1", "unit": "", "desc": "Auto"}}

    # Validate with include filter - should skip params not in include
    api_validator.validate_section("heating", request_data, include=["hvac_mode"])

    # Section should be validated
    assert api_validator.is_section_validated("heating")

    # hvac_mode (700) should still be in config since it was valid
    # Other params should NOT be removed since they weren't in include
    assert "700" in api_validator.api_config["heating"]
    # 710 and 8740 were not validated (skipped), so they remain
    assert "710" in api_validator.api_config["heating"]
    assert "8740" in api_validator.api_config["heating"]


# ========== Additional state() specific tests ==========


@pytest.mark.asyncio
async def test_state_with_include_multiple_params(monkeypatch: Any) -> None:
    """Test state() with multiple parameters in include list."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("heating")
        bsblan._api_validator = api_validator

        state_data = json.loads(load_fixture("state.json"))
        partial_response = {
            "700": state_data["700"],
            "8740": state_data["8740"],
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        state: State = await bsblan.state(include=["hvac_mode", "current_temperature"])

        assert state.hvac_mode is not None
        assert state.hvac_mode.value == 3
        assert state.current_temperature is not None
        assert state.current_temperature.value == 19.3


@pytest.mark.asyncio
async def test_state_with_include_mixed_valid_invalid_params(monkeypatch: Any) -> None:
    """Test state() with mixed valid and invalid parameters.

    Documents intended behavior: valid params are fetched, invalid ones filtered out.
    """
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("heating")
        bsblan._api_validator = api_validator

        state_data = json.loads(load_fixture("state.json"))
        partial_response = {"700": state_data["700"]}

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        state: State = await bsblan.state(
            include=["hvac_mode", "nonexistent_param", "another_invalid"]
        )

        # Verify only valid parameter was requested
        call_args = request_mock.call_args
        assert call_args.kwargs["params"]["Parameter"] == "700"

        assert state.hvac_mode is not None
        assert state.hvac_mode.value == 3
        assert state.target_temperature is None


@pytest.mark.asyncio
async def test_state_without_include(monkeypatch: Any) -> None:
    """Test state() without include parameter fetches all params."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("heating")
        bsblan._api_validator = api_validator

        request_mock: AsyncMock = AsyncMock(
            return_value=json.loads(load_fixture("state.json"))
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        state: State = await bsblan.state()

        assert state.hvac_mode is not None
        assert state.target_temperature is not None
        assert state.current_temperature is not None


# ========== Tests for static_values() with include ==========


@pytest.mark.asyncio
async def test_static_values_with_include(monkeypatch: Any) -> None:
    """Test static_values() with include parameter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        api_validator = APIValidator(API_V3)
        api_validator.validated_sections.add("staticValues")
        bsblan._api_validator = api_validator

        partial_response = {
            "714": {
                "name": "Min temp",
                "unit": "°C",
                "desc": "",
                "value": "8.0",
                "dataType": 0,
                "error": 0,
                "readonly": 0,
                "readwrite": 0,
            },
        }

        request_mock: AsyncMock = AsyncMock(return_value=partial_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        static: StaticState = await bsblan.static_values(include=["min_temp"])

        assert static.min_temp is not None
        assert static.max_temp is None


# ========== Parametrized tests for hot water methods ==========


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "group_name", "test_params"),
    [
        (
            "hot_water_state",
            "essential",
            {
                "param_cache": {"1600": "operating_mode", "1610": "nominal_setpoint"},
                "include_param": "operating_mode",
                "param_id": "1600",
            },
        ),
        (
            "hot_water_config",
            "config",
            {
                "param_cache": {
                    "1645": "legionella_function_setpoint",
                    "1640": "legionella_function",
                },
                "include_param": "legionella_function_setpoint",
                "param_id": "1645",
            },
        ),
        (
            "hot_water_schedule",
            "schedule",
            {
                "param_cache": {
                    "561": "dhw_time_program_monday",
                    "562": "dhw_time_program_tuesday",
                },
                "include_param": "dhw_time_program_monday",
                "param_id": "561",
            },
        ),
    ],
    ids=["hot_water_state", "hot_water_config", "hot_water_schedule"],
)
async def test_hot_water_method_with_include(
    monkeypatch: Any,
    method_name: str,
    group_name: str,
    test_params: dict[str, Any],
) -> None:
    """Test hot water methods with include parameter."""
    param_cache = test_params["param_cache"]
    include_param = test_params["include_param"]
    param_id = test_params["param_id"]

    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        monkeypatch.setattr(bsblan, "_hot_water_param_cache", param_cache)
        bsblan._validated_hot_water_groups.add(group_name)

        # Create mock response
        mock_response = {
            param_id: {
                "name": include_param,
                "value": "1",
                "unit": "",
                "desc": "",
                "dataType": 0,
                "error": 0,
                "readonly": 0,
                "readwrite": 0,
            },
        }

        request_mock: AsyncMock = AsyncMock(return_value=mock_response)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        method = getattr(bsblan, method_name)
        await method(include=[include_param])

        request_mock.assert_awaited_once()
        call_args = request_mock.call_args
        assert call_args.kwargs["params"]["Parameter"] == param_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "group_name", "param_cache"),
    [
        (
            "hot_water_state",
            "essential",
            {"1600": "operating_mode", "1610": "nominal_setpoint"},
        ),
        (
            "hot_water_config",
            "config",
            {"1645": "legionella_function_setpoint"},
        ),
        (
            "hot_water_schedule",
            "schedule",
            {"561": "dhw_time_program_monday"},
        ),
    ],
    ids=["hot_water_state", "hot_water_config", "hot_water_schedule"],
)
async def test_hot_water_method_with_empty_include_list(
    monkeypatch: Any,
    method_name: str,
    group_name: str,
    param_cache: dict[str, str],
) -> None:
    """Test hot water methods with empty include list raises error."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        monkeypatch.setattr(bsblan, "_hot_water_param_cache", param_cache)
        bsblan._validated_hot_water_groups.add(group_name)

        request_mock: AsyncMock = AsyncMock()
        monkeypatch.setattr(bsblan, "_request", request_mock)

        method = getattr(bsblan, method_name)
        with pytest.raises(BSBLANError) as exc_info:
            await method(include=[])

        assert str(exc_info.value) == EMPTY_INCLUDE_LIST_ERROR_MSG
        request_mock.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "group_name", "param_cache"),
    [
        (
            "hot_water_state",
            "essential",
            {"1600": "operating_mode", "1610": "nominal_setpoint"},
        ),
        (
            "hot_water_config",
            "config",
            {"1645": "legionella_function_setpoint"},
        ),
        (
            "hot_water_schedule",
            "schedule",
            {"561": "dhw_time_program_monday"},
        ),
    ],
    ids=["hot_water_state", "hot_water_config", "hot_water_schedule"],
)
async def test_hot_water_method_with_invalid_params(
    monkeypatch: Any,
    method_name: str,
    group_name: str,
    param_cache: dict[str, str],
) -> None:
    """Test hot water methods with all invalid parameters raises error."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)

        monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(bsblan, "_api_data", API_V3)

        monkeypatch.setattr(bsblan, "_hot_water_param_cache", param_cache)
        bsblan._validated_hot_water_groups.add(group_name)

        request_mock: AsyncMock = AsyncMock()
        monkeypatch.setattr(bsblan, "_request", request_mock)

        method = getattr(bsblan, method_name)
        with pytest.raises(BSBLANError) as exc_info:
            await method(include=["nonexistent_param"])

        assert str(exc_info.value) == INVALID_INCLUDE_PARAMS_ERROR_MSG
        request_mock.assert_not_awaited()
