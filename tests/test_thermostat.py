"""Tests for sending values to the BSBLAN device."""

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aiohttp.web_request import Request
from aresponses import Response, ResponsesMockServer

from bsblan import BSBLAN, BSBLANConfig
from bsblan.constants import ErrorMsg
from bsblan.exceptions import (
    BSBLANError,
    BSBLANInvalidParameterError,
)

if TYPE_CHECKING:
    from collections.abc import (
        AsyncGenerator,
        Awaitable,
        Callable,
    )

    from aiohttp.web_request import Request

logger = logging.getLogger(__name__)


@pytest.fixture
async def mock_bsblan() -> AsyncGenerator[BSBLAN, None]:
    """Fixture to create a mocked BSBLAN instance."""
    config = BSBLANConfig(host="example.com")
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(config, session=session)
        bsblan._firmware_version = "1.0.38-20200730234859"
        bsblan._supports_full_config = True
        bsblan._temperature._circuit_temp_ranges[1] = {"min": 17.0, "max": 23.0}
        bsblan._temperature._circuit_temp_initialized.add(1)
        yield bsblan


@pytest.fixture
async def mock_aresponses() -> AsyncGenerator[ResponsesMockServer, None]:
    """Fixture to mock aiohttp responses."""
    async with ResponsesMockServer() as server:
        # Mock response for /JQ
        server.add(
            "example.com",
            "/JQ",
            "POST",
            Response(
                text=json.dumps(
                    {"714.0": {"value": "8.0"}, "716.0": {"value": "30.0"}},
                ),
                content_type="application/json",
            ),
        )
        yield server


def create_response_handler(
    expected_data: dict[str, Any],
) -> Callable[[Request], Awaitable[Response]]:
    """Create a response handler that checks the request data."""

    async def response_handler(request: Request) -> Response:
        """Check the request data."""
        assert request.method == "POST"
        assert request.host == "example.com"
        assert request.path_qs == "/JS"
        actual_data = json.loads(await request.text())

        for key, value in expected_data.items():
            assert key in actual_data, f"Expected key '{key}' not found in actual data"
            if key == "Value":
                # Allow both string and integer representations
                assert str(actual_data[key]) == str(value)
            else:
                assert actual_data[key] == value, (
                    f"Mismatch for key '{key}': expected {value}, "
                    f"got {actual_data[key]}"
                )

        return Response(
            text=json.dumps({"status": "success"}),
            content_type="application/json",
        )

    return response_handler


@pytest.mark.asyncio
async def test_change_temperature(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test changing BSBLAN temperature."""
    expected_data = {
        "Parameter": "710",
        "Value": "20",
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.thermostat(target_temperature="20")


@pytest.mark.asyncio
async def test_first_temperature_write_loads_bounds_lazily(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that temperature validation initializes bounds on demand."""
    mock_bsblan._temperature._circuit_temp_initialized.clear()
    fetch_range = AsyncMock(
        return_value={
            "min": 17.0,
            "max": 23.0,
            "cooling_min": None,
            "cooling_max": None,
        }
    )
    monkeypatch.setattr(
        mock_bsblan._temperature, "_fetch_temperature_range", fetch_range
    )
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler({"Parameter": "710", "Value": "20", "Type": "1"}),
    )

    await mock_bsblan.thermostat(target_temperature="20")

    fetch_range.assert_awaited_once_with(1)
    assert 1 in mock_bsblan._temperature._circuit_temp_initialized


@pytest.mark.asyncio
async def test_change_cooling_temperature(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
) -> None:
    """Test changing BSBLAN cooling setpoint."""
    expected_data = {
        "Parameter": "902",
        "Value": "32.0",
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.thermostat(target_temperature_high=32.0)


@pytest.mark.asyncio
async def test_change_hvac_mode(
    mock_bsblan: BSBLAN,
    mock_aresponses: ResponsesMockServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test changing BSBLAN HVAC mode."""
    mock_bsblan._temperature._circuit_temp_initialized.clear()
    initialize_range = AsyncMock()
    monkeypatch.setattr(
        mock_bsblan._temperature, "initialize_temperature_range", initialize_range
    )
    expected_data = {
        "Parameter": "700",
        "Value": "1",  # 1 corresponds to "auto" mode
        "Type": "1",
    }
    mock_aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.thermostat(hvac_mode=1)  # 1 = auto
    initialize_range.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_temperature(mock_bsblan: BSBLAN) -> None:
    """Test setting an invalid temperature."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.thermostat(target_temperature="35")


@pytest.mark.asyncio
async def test_invalid_cooling_temperature(mock_bsblan: BSBLAN) -> None:
    """Test setting an invalid cooling temperature."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.thermostat(target_temperature_high="invalid")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_mode",
    [
        -1,  # Negative value
        4,  # Just above valid range (0-3)
        99,  # Far outside valid range
    ],
)
async def test_invalid_hvac_mode(mock_bsblan: BSBLAN, invalid_mode: int) -> None:
    """Test setting an invalid HVAC mode."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.thermostat(hvac_mode=invalid_mode)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "valid_mode",
    [
        0,  # off - lower boundary
        1,  # auto
        2,  # reduced
        3,  # heat - upper boundary
    ],
)
async def test_valid_hvac_mode_boundaries(
    mock_bsblan: BSBLAN,
    aresponses: ResponsesMockServer,
    valid_mode: int,
) -> None:
    """Test that all valid HVAC modes (0-3) are accepted."""
    expected_data = {"Parameter": "700", "Value": str(valid_mode), "Type": "1"}
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.thermostat(hvac_mode=valid_mode)


@pytest.mark.asyncio
async def test_no_parameters(
    mock_bsblan: BSBLAN,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test calling thermostat without parameters."""
    initialize_range = AsyncMock()
    monkeypatch.setattr(
        mock_bsblan._temperature, "initialize_temperature_range", initialize_range
    )
    with pytest.raises(BSBLANError) as exc_info:
        await mock_bsblan.thermostat()
    assert str(exc_info.value) == ErrorMsg.MULTI_PARAMETER
    initialize_range.assert_not_awaited()


@pytest.mark.asyncio
async def test_cooling_temperature_with_other_parameter_raises(
    mock_bsblan: BSBLAN,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test cooling setpoint respects one-parameter-per-call rule."""
    initialize_range = AsyncMock()
    monkeypatch.setattr(
        mock_bsblan._temperature, "initialize_temperature_range", initialize_range
    )
    with pytest.raises(BSBLANError) as exc_info:
        await mock_bsblan.thermostat(
            target_temperature="20",
            target_temperature_high="24",
        )
    assert str(exc_info.value) == ErrorMsg.MULTI_PARAMETER
    initialize_range.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_cooling_operating_mode(
    mock_bsblan: BSBLAN,
    aresponses: ResponsesMockServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test setting the cooling operating mode on circuit 1."""
    mock_bsblan._temperature._circuit_temp_initialized.clear()
    initialize_range = AsyncMock()
    monkeypatch.setattr(
        mock_bsblan._temperature, "initialize_temperature_range", initialize_range
    )
    expected_data = {"Parameter": "901", "Value": "1", "Type": "1"}
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.thermostat(cooling_operating_mode=1)
    initialize_range.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_cooling_operating_mode(mock_bsblan: BSBLAN) -> None:
    """Test that an invalid cooling operating mode is rejected."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.thermostat(cooling_operating_mode=99)


@pytest.mark.asyncio
async def test_cooling_operating_mode_with_other_parameter_raises(
    mock_bsblan: BSBLAN,
) -> None:
    """Test cooling operating mode respects one-parameter-per-call rule."""
    with pytest.raises(BSBLANError) as exc_info:
        await mock_bsblan.thermostat(
            hvac_mode=3,
            cooling_operating_mode=1,
        )
    assert str(exc_info.value) == ErrorMsg.MULTI_PARAMETER


@pytest.mark.asyncio
async def test_set_temp_reduced_setpoint(
    mock_bsblan: BSBLAN,
    aresponses: ResponsesMockServer,
) -> None:
    """Test setting the reduced setpoint on circuit 1."""
    expected_data = {"Parameter": "712", "Value": "18.5", "Type": "1"}
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.thermostat(temp_reduced_setpoint=18.5)


@pytest.mark.asyncio
async def test_invalid_temp_reduced_setpoint(mock_bsblan: BSBLAN) -> None:
    """Test that an out-of-range reduced setpoint is rejected."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.thermostat(temp_reduced_setpoint="35")


@pytest.mark.asyncio
@pytest.mark.parametrize("temporary_mode", [0, 1, 2])
async def test_set_temporary_mode(
    mock_bsblan: BSBLAN,
    aresponses: ResponsesMockServer,
    temporary_mode: int,
) -> None:
    """Test setting the temporary operating mode override on circuit 1."""
    expected_data = {
        "Parameter": "10110",
        "Value": str(temporary_mode),
        "Type": "1",
    }
    aresponses.add(
        "example.com",
        "/JS",
        "POST",
        create_response_handler(expected_data),
    )
    await mock_bsblan.thermostat(temporary_mode=temporary_mode)


@pytest.mark.asyncio
@pytest.mark.parametrize("temporary_mode", [-1, 3])
async def test_invalid_temporary_mode(
    mock_bsblan: BSBLAN,
    temporary_mode: int,
) -> None:
    """Test that an invalid temporary operating mode is rejected."""
    with pytest.raises(BSBLANInvalidParameterError):
        await mock_bsblan.thermostat(temporary_mode=temporary_mode)


@pytest.mark.asyncio
async def test_temporary_mode_with_other_parameter_raises(
    mock_bsblan: BSBLAN,
) -> None:
    """Test temporary mode respects one-parameter-per-call rule."""
    with pytest.raises(BSBLANError) as exc_info:
        await mock_bsblan.thermostat(
            temp_reduced_setpoint="18",
            temporary_mode=1,
        )
    assert str(exc_info.value) == ErrorMsg.MULTI_PARAMETER
