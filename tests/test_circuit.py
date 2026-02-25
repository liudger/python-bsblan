"""Tests for multi-circuit (HC1/HC2/HC3) heating support."""

# pylint: disable=protected-access

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aresponses import Response, ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig, State, StaticState
from bsblan.constants import MULTI_PARAMETER_ERROR_MSG, build_api_config
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
        bsblan._api_version = "v3"
        bsblan._api_data = build_api_config("v3")
        bsblan._min_temp = 8.0
        bsblan._max_temp = 30.0
        bsblan._temperature_range_initialized = True

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("heating")
        api_validator.validated_sections.add("heating_circuit2")
        api_validator.validated_sections.add("heating_circuit3")
        api_validator.validated_sections.add("staticValues")
        api_validator.validated_sections.add("staticValues_circuit2")
        api_validator.validated_sections.add("staticValues_circuit3")
        bsblan._api_validator = api_validator

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
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        api_data = build_api_config("v3")
        monkeypatch.setattr(bsblan, "_api_data", api_data)

        api_validator = APIValidator(api_data)
        api_validator.validated_sections.add("heating")
        bsblan._api_validator = api_validator

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
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config("v3"),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("heating_circuit2")
        bsblan._api_validator = api_validator

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
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config("v3"),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("heating_circuit2")
        bsblan._api_validator = api_validator

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
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config("v3"),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("staticValues_circuit2")
        bsblan._api_validator = api_validator

        request_mock = AsyncMock(
            return_value=json.loads(
                load_fixture("static_state_circuit2.json"),
            ),
        )
        monkeypatch.setattr(bsblan, "_request", request_mock)

        static: StaticState = await bsblan.static_values(circuit=2)

        assert isinstance(static, StaticState)
        assert static.min_temp is not None
        assert static.min_temp.value == 8.0
        assert static.max_temp is not None
        assert static.max_temp.value == 28.0


# --- Thermostat tests ---


@pytest.mark.asyncio
async def test_thermostat_circuit2_temperature(
    mock_bsblan_circuit: BSBLAN,
    aresponses: ResponsesMockServer,
) -> None:
    """Test setting temperature on circuit 2."""
    # Set up HC2 temp range
    mock_bsblan_circuit._circuit_temp_ranges[2] = {
        "min": 8.0,
        "max": 28.0,
    }
    mock_bsblan_circuit._circuit_temp_initialized.add(2)

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
    mock_bsblan_circuit._circuit_temp_ranges[2] = {
        "min": 8.0,
        "max": 28.0,
    }
    mock_bsblan_circuit._circuit_temp_initialized.add(2)

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
async def test_thermostat_circuit3_temperature(
    mock_bsblan_circuit: BSBLAN,
    aresponses: ResponsesMockServer,
) -> None:
    """Test setting temperature on circuit 3."""
    mock_bsblan_circuit._circuit_temp_ranges[3] = {
        "min": 8.0,
        "max": 35.0,
    }
    mock_bsblan_circuit._circuit_temp_initialized.add(3)

    expected_data = {
        "Parameter": "1310",
        "Value": "25",
        "Type": "1",
    }
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan_circuit.thermostat(
        target_temperature="25",
        circuit=3,
    )


@pytest.mark.asyncio
async def test_thermostat_circuit3_hvac_mode(
    mock_bsblan_circuit: BSBLAN,
    aresponses: ResponsesMockServer,
) -> None:
    """Test setting HVAC mode on circuit 3."""
    mock_bsblan_circuit._circuit_temp_ranges[3] = {
        "min": 8.0,
        "max": 35.0,
    }
    mock_bsblan_circuit._circuit_temp_initialized.add(3)

    expected_data = {
        "Parameter": "1300",
        "Value": "2",
        "Type": "1",
    }
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan_circuit.thermostat(hvac_mode=2, circuit=3)


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
    mock_bsblan_circuit._circuit_temp_ranges[2] = {
        "min": 8.0,
        "max": 28.0,
    }
    mock_bsblan_circuit._circuit_temp_initialized.add(2)

    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan_circuit.thermostat(
            target_temperature="35",
            circuit=2,
        )


@pytest.mark.asyncio
async def test_thermostat_circuit2_no_temp_range(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test error when HC2 temp range not available."""
    # Set HC2 as initialized but with None range
    mock_bsblan_circuit._circuit_temp_ranges[2] = {
        "min": None,
        "max": None,
    }
    mock_bsblan_circuit._circuit_temp_initialized.add(2)

    with pytest.raises(BSBLANError, match="Temperature range"):
        await mock_bsblan_circuit.thermostat(
            target_temperature="20",
            circuit=2,
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
        await mock_bsblan_circuit.state(circuit=4)

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
    mock_bsblan_circuit._circuit_temp_ranges[2] = {
        "min": 8.0,
        "max": 28.0,
    }
    mock_bsblan_circuit._circuit_temp_initialized.add(2)

    with pytest.raises(BSBLANError) as exc_info:
        await mock_bsblan_circuit.thermostat(circuit=2)
    assert str(exc_info.value) == MULTI_PARAMETER_ERROR_MSG


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
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config("v3"),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("staticValues_circuit2")
        bsblan._api_validator = api_validator

        static_fixture = json.loads(
            load_fixture("static_state_circuit2.json"),
        )
        request_mock = AsyncMock(return_value=static_fixture)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        await bsblan._initialize_temperature_range(circuit=2)

        assert 2 in bsblan._circuit_temp_initialized
        assert bsblan._circuit_temp_ranges[2]["min"] == 8.0
        assert bsblan._circuit_temp_ranges[2]["max"] == 28.0


@pytest.mark.asyncio
async def test_circuit1_temp_range_unchanged(
    monkeypatch: Any,
) -> None:
    """Test that HC1 temp range still uses legacy fields."""
    async with aiohttp.ClientSession() as session:
        config = BSBLANConfig(host="example.com")
        bsblan = BSBLAN(config, session=session)
        monkeypatch.setattr(
            bsblan,
            "_firmware_version",
            "1.0.38-20200730234859",
        )
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        api_data = build_api_config("v3")
        monkeypatch.setattr(bsblan, "_api_data", api_data)

        api_validator = APIValidator(api_data)
        api_validator.validated_sections.add("staticValues")
        bsblan._api_validator = api_validator

        static_fixture = json.loads(
            load_fixture("static_state.json"),
        )
        request_mock = AsyncMock(return_value=static_fixture)
        monkeypatch.setattr(bsblan, "_request", request_mock)

        await bsblan._initialize_temperature_range(circuit=1)

        assert bsblan._temperature_range_initialized
        assert bsblan._min_temp == 8.0
        assert bsblan._max_temp == 20.0
        # HC1 should NOT be in per-circuit storage
        assert 1 not in bsblan._circuit_temp_initialized


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
        monkeypatch.setattr(bsblan, "_api_version", "v3")
        monkeypatch.setattr(
            bsblan,
            "_api_data",
            build_api_config("v3"),
        )

        api_validator = APIValidator(bsblan._api_data)
        api_validator.validated_sections.add("staticValues_circuit2")
        api_validator.validated_sections.add("heating_circuit2")
        bsblan._api_validator = api_validator

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
        assert 2 not in bsblan._circuit_temp_initialized

        # This should trigger lazy init of HC2 temp range
        await bsblan._validate_target_temperature("20.0", circuit=2)

        # Verify it was initialized
        assert 2 in bsblan._circuit_temp_initialized
        assert bsblan._circuit_temp_ranges[2]["min"] == 8.0
        assert bsblan._circuit_temp_ranges[2]["max"] == 28.0


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
        if param_id == "700":
            return {"700": {"value": "1", "unit": "", "desc": "Automatic"}}
        if param_id == "1000":
            return {"1000": {"value": "1", "unit": "", "desc": "Automatic"}}
        # HC3 returns empty
        return {"1300": {}}

    bsblan._request = AsyncMock(side_effect=mock_request)  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1, 2]


@pytest.mark.asyncio
async def test_get_available_circuits_all_three(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test detecting all three available heating circuits."""
    bsblan = mock_bsblan_circuit

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        return {param_id: {"value": "1", "unit": "", "desc": "Automatic"}}

    bsblan._request = AsyncMock(side_effect=mock_request)  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1, 2, 3]


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
        return {param_id: {}}

    bsblan._request = AsyncMock(side_effect=mock_request)  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1]


@pytest.mark.asyncio
async def test_get_available_circuits_request_failure(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test circuit detection when some requests fail."""
    bsblan = mock_bsblan_circuit

    call_count = 0

    async def mock_request(
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        params = kwargs.get("params", {})
        param_id = params.get("Parameter", "")
        if param_id == "700":
            return {"700": {"value": "1", "unit": "", "desc": "Automatic"}}
        # HC2 and HC3 fail with connection error
        msg = "Connection failed"
        raise BSBLANError(msg)

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
        return {"other_key": {"value": "1"}}

    bsblan._request = AsyncMock(side_effect=mock_request)  # type: ignore[method-assign]

    circuits = await bsblan.get_available_circuits()
    assert circuits == [1]


@pytest.mark.asyncio
async def test_state_empty_section_after_validation(
    mock_bsblan_circuit: BSBLAN,
) -> None:
    """Test that fetching state for a circuit with all params removed raises error."""
    bsblan = mock_bsblan_circuit

    # Simulate validation removing all params for heating_circuit2
    assert bsblan._api_validator is not None
    bsblan._api_validator.api_config["heating_circuit2"] = {}  # type: ignore[index]
    bsblan._api_validator.validated_sections.add("heating_circuit2")

    with pytest.raises(BSBLANError, match="No valid parameters found"):
        await bsblan.state(circuit=2)
