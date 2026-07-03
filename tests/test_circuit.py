"""Tests for multi-circuit (HC1/HC2) heating support."""

# pylint: disable=protected-access

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aresponses import Response, ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig, State, StaticState
from bsblan.constants import (
    MIN_SUPPORTED_JSON_API,
    CircuitConfig,
    ErrorMsg,
    build_api_config,
)
from bsblan.exceptions import BSBLANError, BSBLANInvalidParameterError
from bsblan.utility import APIValidator

from . import load_fixture

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from aiohttp.web_request import Request

# --- Fixtures ---


@pytest.fixture
async def mock_bsblan_circuit() -> AsyncGenerator[BSBLAN, None]:
    """Fixture to create a mocked BSBLAN instance for circuit tests."""
    config = BSBLANConfig(host="example.com")
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(config, session=session)
        bsblan._firmware_version = "1.0.38-20200730234859"
        bsblan._supports_full_config = True
        bsblan._api_data = build_api_config()
        bsblan._temperature._circuit_temp_ranges[1] = {"min": 17.0, "max": 23.0}
        bsblan._temperature._circuit_temp_initialized.add(1)

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("heating")
        api_validator.validated_sections.add("heating_circuit2")
        api_validator.validated_sections.add("staticValues")
        api_validator.validated_sections.add("staticValues_circuit2")
        bsblan._validator._api_validator = api_validator

        yield bsblan


def create_response_handler(
    expected_data: dict[str, Any],
) -> Callable[[Request], Awaitable[Response]]:
    """Create a response handler that checks the request data."""

    async def response_handler(request: Request) -> Response:
        """Check the request data."""
        actual_data = json.loads(await request.text())
        for key, value in expected_data.items():
            assert key in actual_data
            if key == "Value":
                assert str(actual_data[key]) == str(value)
            else:
                assert actual_data[key] == value
        return Response(
            text=json.dumps({"status": "success"}),
            content_type="application/json",
        )

    return response_handler


# --- State tests ---


@pytest.mark.asyncio
async def test_state_circuit1_default(monkeypatch: Any) -> None:
    """Test state() defaults to circuit 1."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(
            bsblan,
            "_firmware_version",
            "1.0.38-20200730234859",
        )
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        api_data = build_api_config()
        monkeypatch.setattr(bsblan, "_api_data", api_data)

        api_validator = APIValidator(api_data)
        api_validator.validated_sections.add("heating")
        bsblan._validator._api_validator = api_validator

        request_mock = AsyncMock(
            return_value=json.loads(load_fixture("state.json")),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        state: State = await bsblan.state()

        assert isinstance(state, State)
        assert state.hvac_mode is not None
        assert state.hvac_mode.value == 3
        assert state.target_temperature is not None
        assert state.target_temperature.value == 18.0


@pytest.mark.asyncio
async def test_state_circuit2(monkeypatch: Any) -> None:
    """Test state() with circuit=2 returns HC2 data."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(
            bsblan,
            "_firmware_version",
            "1.0.38-20200730234859",
        )
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config(),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("heating_circuit2")
        bsblan._validator._api_validator = api_validator

        request_mock = AsyncMock(
            return_value=json.loads(
                load_fixture("state_circuit2.json"),
            ),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        state: State = await bsblan.state(circuit=2)

        assert isinstance(state, State)
        assert state.hvac_mode is not None
        assert state.hvac_mode.value == 1
        assert state.hvac_mode.desc == "Automatic"
        assert state.current_temperature is not None
        assert state.current_temperature.value == 18.5
        assert state.target_temperature_high is not None
        assert state.target_temperature_high.value == 24.0
        assert state.cooling_operating_mode is not None
        assert state.cooling_operating_mode.value == 0
        assert state.cooling_operating_mode.desc == "Protection"


@pytest.mark.asyncio
async def test_state_circuit2_with_include(monkeypatch: Any) -> None:
    """Test state() with circuit=2 and include filter."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(
            bsblan,
            "_firmware_version",
            "1.0.38-20200730234859",
        )
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config(),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("heating_circuit2")
        bsblan._validator._api_validator = api_validator

        # Only return hvac_mode data
        request_mock = AsyncMock(
            return_value={
                "1000": json.loads(
                    load_fixture("state_circuit2.json"),
                )["1000"],
            },
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        state: State = await bsblan.state(
            circuit=2,
            include=["hvac_mode"],
        )

        assert isinstance(state, State)
        assert state.hvac_mode is not None
        assert state.hvac_mode.value == 1


# --- Static values tests ---


@pytest.mark.asyncio
async def test_static_values_circuit2(monkeypatch: Any) -> None:
    """Test static_values() with circuit=2."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(
            bsblan,
            "_firmware_version",
            "1.0.38-20200730234859",
        )
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config(),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("staticValues_circuit2")
        bsblan._validator._api_validator = api_validator

        request_mock = AsyncMock(
            return_value=json.loads(
                load_fixture("static_state_circuit2.json"),
            ),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        static: StaticState = await bsblan.static_values(circuit=2)

        assert isinstance(static, StaticState)
        assert static.temp_reduced_setpoint is not None
        assert static.temp_reduced_setpoint.value == 16.0
        assert static.comfort_setpoint_max is not None
        assert static.comfort_setpoint_max.value == 28.0
        assert static.heating_protective_setpoint is not None
        assert static.heating_protective_setpoint.value == 8.0
        assert static.cooling_comfort_setpoint_min is not None
        assert static.cooling_comfort_setpoint_min.value == 18.0
        assert static.cooling_reduced_setpoint is not None
        assert static.cooling_reduced_setpoint.value == 26.0


# --- Thermostat tests ---


@pytest.mark.asyncio
async def test_thermostat_circuit2_temperature(
    mock_bsblan_circuit: BSBLAN,
    aresponses: ResponsesMockServer,
) -> None:
    """Test setting temperature on circuit 2."""
    # Set up HC2 temp range
    mock_bsblan_circuit._temperature._circuit_temp_ranges[2] = {
        "min": 16.0,
        "max": 28.0,
    }
    mock_bsblan_circuit._temperature._circuit_temp_initialized.add(2)

    expected_data = {
        "Parameter": "1010",
        "Value": "20",
        "Type": "1",
    }
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan_circuit.thermostat(
        target_temperature="20",
        circuit=2,
    )


@pytest.mark.asyncio
async def test_thermostat_circuit2_hvac_mode(
    mock_bsblan_circuit: BSBLAN,
    aresponses: ResponsesMockServer,
) -> None:
    """Test setting HVAC mode on circuit 2."""
    # Set up HC2 temp range
    mock_bsblan_circuit._temperature._circuit_temp_ranges[2] = {
        "min": 16.0,
        "max": 28.0,
    }
    mock_bsblan_circuit._temperature._circuit_temp_initialized.add(2)

    expected_data = {
        "Parameter": "1000",
        "Value": "1",
        "Type": "1",
    }
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan_circuit.thermostat(hvac_mode=1, circuit=2)


@pytest.mark.asyncio
async def test_thermostat_circuit1_still_works(
    mock_bsblan_circuit: BSBLAN,
    aresponses: ResponsesMockServer,
) -> None:
    """Test that circuit=1 (default) still uses HC1 parameters."""
    expected_data = {
        "Parameter": "710",
        "Value": "20",
        "Type": "1",
    }
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan_circuit.thermostat(target_temperature="20")


@pytest.mark.asyncio
async def test_thermostat_circuit2_invalid_temperature(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test setting out-of-range temperature on circuit 2."""
    mock_bsblan_circuit._temperature._circuit_temp_ranges[2] = {
        "min": 16.0,
        "max": 28.0,
    }
    mock_bsblan_circuit._temperature._circuit_temp_initialized.add(2)

    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan_circuit.thermostat(
            target_temperature="35",
            circuit=2,
        )


@pytest.mark.asyncio
async def test_thermostat_circuit2_no_temp_range(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test thermostat passes through when HC2 temp range not available."""
    # Set HC2 as initialized but with None range
    mock_bsblan_circuit._temperature._circuit_temp_ranges[2] = {
        "min": None,
        "max": None,
    }
    mock_bsblan_circuit._temperature._circuit_temp_initialized.add(2)

    # Should pass through without range validation when min/max are None
    mock_bsblan_circuit._request = AsyncMock(return_value={"status": "success"})
    await mock_bsblan_circuit.thermostat(
        target_temperature="20",
        circuit=2,
    )
    mock_bsblan_circuit._request.assert_awaited_once_with(
        base_path="/JS",
        data={"Parameter": "1010", "Value": "20", "Type": "1"},
    )


# --- Validation tests ---


@pytest.mark.asyncio
async def test_invalid_circuit_number(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test that invalid circuit numbers are rejected."""
    with pytest.raises(BSBLANInvalidParameterError, match="Invalid circuit"):
        await mock_bsblan_circuit.state(circuit=0)

    with pytest.raises(BSBLANInvalidParameterError, match="Invalid circuit"):
        await mock_bsblan_circuit.state(circuit=3)

    with pytest.raises(BSBLANInvalidParameterError, match="Invalid circuit"):
        await mock_bsblan_circuit.static_values(circuit=99)


@pytest.mark.asyncio
async def test_invalid_circuit_thermostat(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test that invalid circuit numbers are rejected for thermostat."""
    with pytest.raises(BSBLANInvalidParameterError, match="Invalid circuit"):
        await mock_bsblan_circuit.thermostat(
            target_temperature="20",
            circuit=0,
        )


@pytest.mark.asyncio
async def test_thermostat_circuit2_no_params(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test that multi-parameter error still works with circuit."""
    mock_bsblan_circuit._temperature._circuit_temp_ranges[2] = {
        "min": 16.0,
        "max": 28.0,
    }
    mock_bsblan_circuit._temperature._circuit_temp_initialized.add(2)

    with pytest.raises(BSBLANError) as exc_info:
        await mock_bsblan_circuit.thermostat(circuit=2)
    assert str(exc_info.value) == ErrorMsg.MULTI_PARAMETER


@pytest.mark.asyncio
async def test_thermostat_circuit2_cooling_temperature(
    mock_bsblan_circuit: BSBLAN,
    aresponses: ResponsesMockServer,
) -> None:
    """Test setting cooling temperature on circuit 2."""
    mock_bsblan_circuit._temperature._circuit_temp_ranges[2] = {
        "min": 16.0,
        "max": 28.0,
        "cooling_min": 18.0,
        "cooling_max": 26.0,
    }
    mock_bsblan_circuit._temperature._circuit_temp_initialized.add(2)

    expected_data = {
        "Parameter": "1202",
        "Value": "24",
        "Type": "1",
    }
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan_circuit.thermostat(
        target_temperature_high="24",
        circuit=2,
    )


@pytest.mark.asyncio
async def test_thermostat_circuit2_invalid_cooling_temperature(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test setting out-of-range cooling temperature on circuit 2."""
    mock_bsblan_circuit._temperature._circuit_temp_ranges[2] = {
        "cooling_min": 18.0,
        "cooling_max": 26.0,
    }
    mock_bsblan_circuit._temperature._circuit_temp_initialized.add(2)

    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan_circuit.thermostat(
            target_temperature_high="17",
            circuit=2,
        )


@pytest.mark.asyncio
async def test_thermostat_circuit2_cooling_operating_mode(
    mock_bsblan_circuit: BSBLAN,
    aresponses: ResponsesMockServer,
) -> None:
    """Test setting the cooling operating mode on circuit 2."""
    mock_bsblan_circuit._temperature._circuit_temp_ranges[2] = {
        "min": 16.0,
        "max": 28.0,
    }
    mock_bsblan_circuit._temperature._circuit_temp_initialized.add(2)

    expected_data = {
        "Parameter": "1201",
        "Value": "0",
        "Type": "1",
    }
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan_circuit.thermostat(
        cooling_operating_mode=0,
        circuit=2,
    )


# --- Temperature range initialization tests ---


@pytest.mark.asyncio
async def test_circuit2_temp_range_initialization(
    monkeypatch: Any,
) -> None:
    """Test that HC2 temperature range initializes from static values."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(
            bsblan,
            "_firmware_version",
            "1.0.38-20200730234859",
        )
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config(),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("staticValues_circuit2")
        bsblan._validator._api_validator = api_validator

        static_fixture = json.loads(
            load_fixture("static_state_circuit2.json"),
        )
        request_mock = AsyncMock(return_value=static_fixture)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        await bsblan._initialize_temperature_range(circuit=2)

        assert 2 in bsblan._temperature._circuit_temp_initialized
        assert bsblan._temperature._circuit_temp_ranges[2]["min"] == 8.0
        assert bsblan._temperature._circuit_temp_ranges[2]["max"] == 28.0
        assert bsblan._temperature._circuit_temp_ranges[2]["cooling_min"] == 18.0
        assert bsblan._temperature._circuit_temp_ranges[2]["cooling_max"] == 26.0


@pytest.mark.asyncio
async def test_circuit1_temp_range_uses_protective_lower_bound(
    monkeypatch: Any,
) -> None:
    """Test that HC1 temp range uses the protective setpoint lower bound."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(
            bsblan,
            "_firmware_version",
            "1.0.38-20200730234859",
        )
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        api_data = build_api_config()
        monkeypatch.setattr(bsblan, "_api_data", api_data)

        api_validator = APIValidator(api_data)
        api_validator.validated_sections.add("staticValues")
        bsblan._validator._api_validator = api_validator

        static_fixture = json.loads(
            load_fixture("static_state.json"),
        )
        request_mock = AsyncMock(return_value=static_fixture)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        await bsblan._initialize_temperature_range(circuit=1)

        assert 1 in bsblan._temperature._circuit_temp_initialized
        # Lower bound is the protective/frost setpoint (714 = 8.0), not the
        # reduced setpoint (712 = 17.0).
        assert bsblan._temperature._circuit_temp_ranges[1]["min"] == 8.0
        assert bsblan._temperature._circuit_temp_ranges[1]["max"] == 23.0

        with pytest.raises(BSBLANInvalidParameterError):
            await bsblan._validate_target_temperature("7.5", circuit=1)


@pytest.mark.asyncio
async def test_thermostat_circuit2_lazy_temp_init(
    monkeypatch: Any,
) -> None:
    """Test that HC2 thermostat lazy-initializes temp range."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(
            bsblan,
            "_firmware_version",
            "1.0.38-20200730234859",
        )
        monkeypatch.setattr(bsblan, "_supports_full_config", True)
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config(),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("staticValues_circuit2")
        api_validator.validated_sections.add("heating_circuit2")
        bsblan._validator._api_validator = api_validator

        # First: mock _request to return static values for temp range
        static_fixture = json.loads(
            load_fixture("static_state_circuit2.json"),
        )

        call_count = 0

        async def mock_request(**_kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: static values for temp range init
                return static_fixture
            # Second call: thermostat set
            return {"status": "success"}

        monkeypatch.setattr(bsblan, "_request", mock_request)

        # HC2 temp range is NOT initialized yet
        assert 2 not in bsblan._temperature._circuit_temp_initialized

        # This should trigger lazy init of HC2 temp range
        await bsblan._validate_target_temperature("20.0", circuit=2)

        # Verify it was initialized
        assert 2 in bsblan._temperature._circuit_temp_initialized
        assert bsblan._temperature._circuit_temp_ranges[2]["min"] == 8.0
        assert bsblan._temperature._circuit_temp_ranges[2]["max"] == 28.0


# --- Tests for get_available_circuits ---


@pytest.mark.asyncio
async def test_get_available_circuits_two_circuits(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test detecting two available heating circuits."""
    bsblan = mock_bsblan_circuit

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        # HC1 operating mode
        if param_id == "700":
            return {"700": {"value": "1", "unit": "", "desc": "Automatic"}}
        # HC2 operating mode
        if param_id == "1000":
            return {"1000": {"value": "1", "unit": "", "desc": "Automatic"}}
        msg = f"Unexpected parameter probe: {param_id}"
        raise AssertionError(msg)

    request_mock = AsyncMock(side_effect=mock_request)
    bsblan._request = request_mock  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1, 2]
    assert bsblan._available_circuits == {1, 2}
    assert [
        call.kwargs["params"]["Parameter"] for call in request_mock.await_args_list
    ] == ["700", "1000"]


@pytest.mark.asyncio
async def test_get_available_circuits_only_one(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test detecting only one available heating circuit."""
    bsblan = mock_bsblan_circuit

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        if param_id == "700":
            return {"700": {"value": "3", "unit": "", "desc": "Comfort"}}
        # HC2 operating mode - return empty
        if param_id == "1000":
            return {param_id: {}}
        msg = f"Unexpected parameter probe: {param_id}"
        raise AssertionError(msg)

    request_mock = AsyncMock(side_effect=mock_request)
    bsblan._request = request_mock  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1]
    assert bsblan._available_circuits == {1}
    assert [
        call.kwargs["params"]["Parameter"] for call in request_mock.await_args_list
    ] == ["700", "1000"]


@pytest.mark.asyncio
async def test_get_available_circuits_does_not_probe_status_params(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test discovery only queries probe params, not status params."""
    bsblan = mock_bsblan_circuit

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        # All circuits return valid operating mode
        if param_id in {"700", "1000"}:
            return {param_id: {"value": "1", "unit": "", "desc": "Automatic"}}
        msg = f"Unexpected status parameter probe: {param_id}"
        raise AssertionError(msg)

    request_mock = AsyncMock(side_effect=mock_request)
    bsblan._request = request_mock  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1, 2]
    assert {
        call.kwargs["params"]["Parameter"] for call in request_mock.await_args_list
    } == {
        "700",
        "1000",
    }


@pytest.mark.asyncio
async def test_get_available_circuits_request_failure(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test circuit detection when some requests fail."""
    bsblan = mock_bsblan_circuit

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        if param_id == "700":
            return {"700": {"value": "1", "unit": "", "desc": "Automatic"}}
        # HC2 fail with connection error
        if param_id == "1000":
            msg = "Connection failed"
            raise BSBLANError(msg)
        msg = f"Unexpected parameter probe: {param_id}"
        raise AssertionError(msg)

    bsblan._request = AsyncMock(side_effect=mock_request)  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1]


@pytest.mark.asyncio
async def test_get_available_circuits_param_not_in_response(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test circuit detection when param ID is missing from response."""
    bsblan = mock_bsblan_circuit

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        if param_id == "700":
            return {"700": {"value": "1", "unit": "", "desc": "Automatic"}}
        # Returns a response but without the expected param key
        if param_id == "1000":
            return {"other_key": {"value": "1"}}
        msg = f"Unexpected parameter probe: {param_id}"
        raise AssertionError(msg)

    bsblan._request = AsyncMock(side_effect=mock_request)  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1]


@pytest.mark.asyncio
async def test_get_available_circuits_all_probes_missing(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test no circuits are detected when operating mode probes are missing."""
    bsblan = mock_bsblan_circuit
    expected_params = list(CircuitConfig.PROBE_PARAMS.values())

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        if param_id in expected_params:
            return {}
        msg = f"Unexpected parameter probe: {param_id}"
        raise AssertionError(msg)

    request_mock = AsyncMock(side_effect=mock_request)
    bsblan._request = request_mock  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == []
    assert bsblan._available_circuits == set()
    assert [
        call.kwargs["params"]["Parameter"] for call in request_mock.await_args_list
    ] == expected_params


@pytest.mark.asyncio
async def test_get_available_circuits_inactive_marker_excludes_circuit(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test a circuit whose probe value is "---" is excluded."""
    bsblan = mock_bsblan_circuit

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        if param_id == "700":
            return {"700": {"value": "1", "unit": "", "desc": "Automatic"}}
        # HC2 reports the inactive marker value
        if param_id == "1000":
            return {"1000": {"value": "---", "unit": "", "desc": ""}}
        msg = f"Unexpected parameter probe: {param_id}"
        raise AssertionError(msg)

    bsblan._request = AsyncMock(side_effect=mock_request)  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1]
    assert bsblan._available_circuits == {1}


@pytest.mark.asyncio
async def test_get_available_circuits_none_value_excludes_circuit(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test a circuit whose probe value is None is excluded."""
    bsblan = mock_bsblan_circuit

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        if param_id == "700":
            return {"700": {"value": "1", "unit": "", "desc": "Automatic"}}
        if param_id == "1000":
            return {"1000": {"value": None, "unit": "", "desc": ""}}
        msg = f"Unexpected parameter probe: {param_id}"
        raise AssertionError(msg)

    bsblan._request = AsyncMock(side_effect=mock_request)  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1]
    assert bsblan._available_circuits == {1}


@pytest.mark.asyncio
async def test_get_available_circuits_json_api_v1_skips_discovery(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test that JSON-API version 1.0 skips circuit discovery and returns [1]."""
    bsblan = mock_bsblan_circuit
    bsblan._json_api_version = MIN_SUPPORTED_JSON_API

    request_mock = AsyncMock()
    bsblan._request = request_mock  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()

    assert circuits == [1]
    assert bsblan._available_circuits == {1}
    request_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_temperature_range_skips_unavailable_discovered_circuit(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test temp range init skips circuits known unavailable from discovery."""
    bsblan = mock_bsblan_circuit
    bsblan._available_circuits = {1}
    request_mock = AsyncMock(return_value={})
    bsblan._request = request_mock  # type: ignore[method-assign]

    await bsblan._initialize_temperature_range(circuit=2)

    assert 2 in bsblan._temperature._circuit_temp_initialized
    assert bsblan._temperature._circuit_temp_ranges[2] == {
        "min": None,
        "max": None,
        "cooling_min": None,
        "cooling_max": None,
    }
    request_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_state_empty_section_after_validation(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test that fetching state for a circuit with all params removed raises error."""
    bsblan = mock_bsblan_circuit

    # Simulate validation removing all params for heating_circuit2
    assert bsblan._validator._api_validator is not None
    bsblan._validator._api_validator.api_config["heating_circuit2"] = {}  # type: ignore[index]
    bsblan._validator._api_validator.validated_sections.add("heating_circuit2")

    with pytest.raises(BSBLANError, match="No valid parameters found"):
        await bsblan.state(circuit=2)
