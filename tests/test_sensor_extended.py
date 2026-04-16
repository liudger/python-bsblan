"""Tests for extended diagnostic sensor methods."""

# pylint: disable=duplicate-code
# pylint: disable=protected-access

import json
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import (
    BSBLAN,
    BSBLANConfig,
    BSBLANError,
    SensorDiagnostic,
    SensorPerformance,
    SensorTemperature,
)
from bsblan.constants import (
    API_V3,
    SENSOR_DIAGNOSTIC_PARAMS,
    SENSOR_PERFORMANCE_PARAMS,
    SENSOR_TEMPERATURE_PARAMS,
)
from bsblan.utility import APIValidator

from . import load_fixture


def _make_bsblan(
    monkeypatch: Any,
    session: aiohttp.ClientSession,
) -> BSBLAN:
    """Create a BSBLAN instance with basic setup for testing."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config, session=session)
    monkeypatch.setattr(bsblan, "_firmware_version", "1.0.38-20200730234859")
    monkeypatch.setattr(bsblan, "_api_version", "v3")
    monkeypatch.setattr(bsblan, "_api_data", API_V3)
    api_validator = APIValidator(API_V3)
    api_validator.validated_sections.add("sensor")
    bsblan._api_validator = api_validator
    return bsblan


def _mock_request_from_fixture(
    fixture_data: dict[str, Any],
) -> AsyncMock:
    """Create a mock _request that returns fixture data by param IDs."""

    def mock_request(**kwargs: Any) -> dict[str, Any]:
        param_string = kwargs.get("params", {}).get("Parameter", "")
        if param_string:
            requested_ids = param_string.split(",")
            return {
                pid: fixture_data[pid] for pid in requested_ids if pid in fixture_data
            }
        return fixture_data

    return AsyncMock(side_effect=mock_request)


# ── Temperature sensor tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_sensor_temperature(monkeypatch: Any) -> None:
    """Test getting extended temperature sensor readings."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache(dict(SENSOR_TEMPERATURE_PARAMS))
        bsblan._validated_sensor_groups.add("temperature")

        fixture = json.loads(load_fixture("sensor_temperature.json"))
        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_temperature()

        assert isinstance(result, SensorTemperature)
        assert result.boiler_temperature is not None
        assert result.boiler_temperature.value == 62.3
        assert result.return_temperature is not None
        assert result.return_temperature.value == 45.1
        assert result.flue_gas_temperature is not None
        assert result.flue_gas_temperature.value == 128.5
        assert result.outside_temperature_damped is not None
        assert result.outside_temperature_damped.value == 6.8
        assert result.flow_temperature_hc1 is not None
        assert result.flow_temperature_hc1.value == 55.2
        assert result.flow_temperature_hc2 is not None
        assert result.flow_temperature_hc2.value == 42.0


@pytest.mark.asyncio
async def test_sensor_temperature_with_include(monkeypatch: Any) -> None:
    """Test temperature sensors with include filter."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache(dict(SENSOR_TEMPERATURE_PARAMS))
        bsblan._validated_sensor_groups.add("temperature")

        fixture = json.loads(load_fixture("sensor_temperature.json"))
        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_temperature(
            include=["boiler_temperature", "return_temperature"]
        )

        assert isinstance(result, SensorTemperature)
        assert result.boiler_temperature is not None
        assert result.boiler_temperature.value == 62.3
        assert result.return_temperature is not None
        assert result.return_temperature.value == 45.1


@pytest.mark.asyncio
async def test_sensor_temperature_no_params_error(monkeypatch: Any) -> None:
    """Test error when no temperature sensor parameters available."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache({})
        bsblan._validated_sensor_groups.add("temperature")

        with pytest.raises(BSBLANError, match="No temperature sensor"):
            await bsblan.sensor_temperature()


# ── Diagnostic sensor tests ───────────────────────────────────────


@pytest.mark.asyncio
async def test_sensor_diagnostic(monkeypatch: Any) -> None:
    """Test getting diagnostic sensor readings."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache(dict(SENSOR_DIAGNOSTIC_PARAMS))
        bsblan._validated_sensor_groups.add("diagnostic")

        fixture = json.loads(load_fixture("sensor_diagnostic.json"))
        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_diagnostic()

        assert isinstance(result, SensorDiagnostic)
        assert result.status_dhw is not None
        assert result.status_dhw.value == 118
        assert result.status_boiler is not None
        assert result.status_boiler.value == 114
        assert result.fan_speed is not None
        assert result.fan_speed.value == 2850
        assert result.burner_modulation is not None
        assert result.burner_modulation.value == 72.5
        assert result.water_pressure is not None
        assert result.water_pressure.value == 1.8
        assert result.boiler_pump_modulation is not None
        assert result.boiler_pump_modulation.value == 85.0


@pytest.mark.asyncio
async def test_sensor_diagnostic_with_include(monkeypatch: Any) -> None:
    """Test diagnostic sensors with include filter."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache(dict(SENSOR_DIAGNOSTIC_PARAMS))
        bsblan._validated_sensor_groups.add("diagnostic")

        fixture = json.loads(load_fixture("sensor_diagnostic.json"))
        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_diagnostic(
            include=["water_pressure", "burner_modulation"]
        )

        assert isinstance(result, SensorDiagnostic)
        assert result.water_pressure is not None
        assert result.water_pressure.value == 1.8
        assert result.burner_modulation is not None
        assert result.burner_modulation.value == 72.5


@pytest.mark.asyncio
async def test_sensor_diagnostic_no_params_error(monkeypatch: Any) -> None:
    """Test error when no diagnostic sensor parameters available."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache({})
        bsblan._validated_sensor_groups.add("diagnostic")

        with pytest.raises(BSBLANError, match="No diagnostic sensor"):
            await bsblan.sensor_diagnostic()


# ── Performance sensor tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_sensor_performance(monkeypatch: Any) -> None:
    """Test getting performance counter readings."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache(dict(SENSOR_PERFORMANCE_PARAMS))
        bsblan._validated_sensor_groups.add("performance")

        fixture = json.loads(load_fixture("sensor_performance.json"))
        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_performance()

        assert isinstance(result, SensorPerformance)
        assert result.operating_hours_heating is not None
        assert result.operating_hours_heating.value == 12450
        assert result.burner_starts is not None
        assert result.burner_starts.value == 8523
        assert result.burner_hours_stage1 is not None
        assert result.burner_hours_stage1.value == 9870
        assert result.burner_hours_dhw is not None
        assert result.burner_hours_dhw.value == 3240


@pytest.mark.asyncio
async def test_sensor_performance_with_include(monkeypatch: Any) -> None:
    """Test performance sensors with include filter."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache(dict(SENSOR_PERFORMANCE_PARAMS))
        bsblan._validated_sensor_groups.add("performance")

        fixture = json.loads(load_fixture("sensor_performance.json"))
        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_performance(
            include=["operating_hours_heating", "burner_starts"]
        )

        assert isinstance(result, SensorPerformance)
        assert result.operating_hours_heating is not None
        assert result.operating_hours_heating.value == 12450
        assert result.burner_starts is not None
        assert result.burner_starts.value == 8523


@pytest.mark.asyncio
async def test_sensor_performance_no_params_error(monkeypatch: Any) -> None:
    """Test error when no performance sensor parameters available."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache({})
        bsblan._validated_sensor_groups.add("performance")

        with pytest.raises(BSBLANError, match="No performance sensor"):
            await bsblan.sensor_performance()


# ── Include filter edge cases ─────────────────────────────────────


@pytest.mark.asyncio
async def test_sensor_empty_include_error(monkeypatch: Any) -> None:
    """Test error when empty include list is provided."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache(dict(SENSOR_TEMPERATURE_PARAMS))
        bsblan._validated_sensor_groups.add("temperature")

        with pytest.raises(BSBLANError, match="Empty include list"):
            await bsblan.sensor_temperature(include=[])


@pytest.mark.asyncio
async def test_sensor_invalid_include_error(monkeypatch: Any) -> None:
    """Test error when include list has no valid parameters."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache(dict(SENSOR_TEMPERATURE_PARAMS))
        bsblan._validated_sensor_groups.add("temperature")

        with pytest.raises(BSBLANError, match="None of the requested"):
            await bsblan.sensor_temperature(include=["nonexistent_param"])


# ── Lazy validation tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_sensor_group_lazy_validation(monkeypatch: Any) -> None:
    """Test that sensor groups are validated lazily on first access."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        # Don't pre-validate — let lazy loading happen
        fixture = json.loads(load_fixture("sensor_temperature.json"))
        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_temperature()

        assert isinstance(result, SensorTemperature)
        assert "temperature" in bsblan._validated_sensor_groups
        assert len(bsblan._sensor_param_cache) == 6


@pytest.mark.asyncio
async def test_sensor_group_validation_skips_unsupported(
    monkeypatch: Any,
) -> None:
    """Test that unsupported params are removed during validation."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        # Return fixture with one param returning "---"
        fixture = json.loads(load_fixture("sensor_temperature.json"))
        fixture["8773"]["value"] = "---"

        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_temperature()

        assert isinstance(result, SensorTemperature)
        assert "temperature" in bsblan._validated_sensor_groups
        # 8773 should be removed from cache
        assert "8773" not in bsblan._sensor_param_cache
        assert len(bsblan._sensor_param_cache) == 5


@pytest.mark.asyncio
async def test_sensor_group_validation_skips_missing(
    monkeypatch: Any,
) -> None:
    """Test that missing params are removed during validation."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        # Return fixture with one param completely missing
        fixture = json.loads(load_fixture("sensor_temperature.json"))
        del fixture["8316"]

        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_temperature()

        assert isinstance(result, SensorTemperature)
        assert "8316" not in bsblan._sensor_param_cache
        assert len(bsblan._sensor_param_cache) == 5


@pytest.mark.asyncio
async def test_sensor_group_not_revalidated(monkeypatch: Any) -> None:
    """Test that already-validated groups skip validation."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        bsblan.set_sensor_cache(dict(SENSOR_DIAGNOSTIC_PARAMS))
        bsblan._validated_sensor_groups.add("diagnostic")

        fixture = json.loads(load_fixture("sensor_diagnostic.json"))
        mock = _mock_request_from_fixture(fixture)
        monkeypatch.setattr(bsblan, "_request", mock)

        await bsblan.sensor_diagnostic()
        await bsblan.sensor_diagnostic()

        # _request called twice for data fetch, but validation skipped
        assert mock.call_count == 2


@pytest.mark.asyncio
async def test_sensor_validation_with_include_filter(
    monkeypatch: Any,
) -> None:
    """Test lazy validation respects include filter."""
    async with aiohttp.ClientSession() as session:
        bsblan = _make_bsblan(monkeypatch, session)

        # Only provide the params we're including in fixture
        fixture = {
            "8310": json.loads(load_fixture("sensor_temperature.json"))["8310"],
        }
        monkeypatch.setattr(bsblan, "_request", _mock_request_from_fixture(fixture))

        result = await bsblan.sensor_temperature(include=["boiler_temperature"])

        assert isinstance(result, SensorTemperature)
        assert result.boiler_temperature is not None
        assert result.boiler_temperature.value == 62.3
        # Only the included param should be in cache
        assert len(bsblan._sensor_param_cache) == 1
        assert "8310" in bsblan._sensor_param_cache
