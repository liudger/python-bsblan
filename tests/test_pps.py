"""Tests for minimal PPS bus support."""

# pylint: disable=protected-access

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from bsblan import BSBLAN, BSBLANConfig, Device, State, StaticState
from bsblan.constants import (
    PPS_HEATING_PARAMS,
    PPS_STATIC_VALUES_PARAMS,
    ErrorMsg,
    build_api_config,
)
from bsblan.exceptions import BSBLANError, BSBLANInvalidParameterError
from bsblan.utility import APIValidator

from . import load_fixture

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def pps_bsblan() -> AsyncGenerator[BSBLAN, None]:
    """Create a PPS BSBLAN instance with bus-specific API data."""
    config = BSBLANConfig(host="example.com")
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(config, session=session)
        bsblan._firmware_version = "5.1.0"
        bsblan._api_version = "v3"
        bsblan._device = Device.model_validate(
            json.loads(load_fixture("pps_device.json"))
        )
        bsblan._api_data = build_api_config("v3")
        bsblan._apply_bus_specific_api_config()
        bsblan._validator._api_validator = APIValidator(bsblan._api_data)
        yield bsblan


def test_pps_device_capabilities() -> None:
    """Test PPS metadata and derived capabilities."""
    device = Device.model_validate(json.loads(load_fixture("pps_device.json")))

    assert device.bus == "PPS"
    assert device.buswritable == 1
    assert device.busaddr == 0
    assert device.busdest == 0
    assert device.is_pps_bus
    assert device.is_bus_writable
    assert not device.supports_time_sync


def test_bsb_device_capabilities() -> None:
    """Test BSB metadata keeps time sync available when writable."""
    device = Device.model_validate(json.loads(load_fixture("device.json")))

    assert device.bus == "BSB"
    assert not device.is_pps_bus
    assert device.is_bus_writable
    assert device.supports_time_sync


def test_bsb_device_with_buswritable_zero_supports_time_sync() -> None:
    """Test BSB time sync does not depend on global bus write metadata."""
    device = Device(
        name="BSB-LAN",
        version="5.1.0",
        MAC="00:80:41:19:69:92",
        uptime=1,
        bus="BSB",
        buswritable=0,
    )

    assert not device.is_bus_writable
    assert device.supports_time_sync


def test_device_without_bus_metadata_keeps_bsb_defaults() -> None:
    """Test older /JI responses without bus metadata keep standard behavior."""
    device = Device(
        name="BSB-LAN",
        version="1.0.38-20200730234859",
        MAC="00:80:41:19:69:90",
        uptime=1,
    )

    assert not device.is_pps_bus
    assert device.is_bus_writable
    assert device.supports_time_sync


def test_client_time_sync_support_requires_device_metadata() -> None:
    """Test clients report time sync support only after device metadata loads."""
    bsblan = BSBLAN(BSBLANConfig(host="example.com"))

    assert bsblan.device_info is None
    assert not bsblan.supports_time_sync


def test_pps_api_config_uses_climate_params(pps_bsblan: BSBLAN) -> None:
    """Test PPS devices use the 15000+ climate parameter map."""
    assert pps_bsblan.device_info is not None
    assert pps_bsblan.supports_time_sync is False
    assert pps_bsblan._api_data is not None
    assert pps_bsblan._api_data["heating"] == PPS_HEATING_PARAMS
    assert pps_bsblan._api_data["staticValues"] == PPS_STATIC_VALUES_PARAMS
    assert pps_bsblan._api_data["heating_circuit2"] == {}
    assert pps_bsblan._api_data["staticValues_circuit2"] == {}


@pytest.mark.asyncio
async def test_pps_set_time_raises_without_posting(pps_bsblan: BSBLAN) -> None:
    """Test PPS devices refuse normal parameter 0 time sync writes."""
    request_mock = AsyncMock(return_value={"status": "ok"})
    pps_bsblan._request = request_mock  # type: ignore[method-assign]

    with pytest.raises(BSBLANError, match=ErrorMsg.TIME_SYNC_NOT_SUPPORTED):
        await pps_bsblan.set_time("01.01.2024 12:30:45")

    request_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_pps_time_raises_without_querying_param_zero(
    pps_bsblan: BSBLAN,
) -> None:
    """Test PPS devices refuse normal parameter 0 time reads."""
    request_mock = AsyncMock(return_value=json.loads(load_fixture("time.json")))
    pps_bsblan._request = request_mock  # type: ignore[method-assign]

    with pytest.raises(BSBLANError, match=ErrorMsg.TIME_SYNC_NOT_SUPPORTED):
        await pps_bsblan.time()

    request_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_time_refreshes_device_when_initialized() -> None:
    """Test initialized clients refresh missing device metadata before time sync."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._firmware_version = "5.1.0"
        bsblan._api_version = "v3"
        bsblan._initialized = True
        request_mock = AsyncMock(
            side_effect=[
                json.loads(load_fixture("device.json")),
                json.loads(load_fixture("time.json")),
            ]
        )
        bsblan._request = request_mock  # type: ignore[method-assign]

        await bsblan.time()

    assert request_mock.await_args_list[0].kwargs == {"base_path": "/JI"}
    assert request_mock.await_args_list[1].kwargs == {"params": {"Parameter": "0"}}


@pytest.mark.asyncio
async def test_set_time_fetches_device_metadata_before_sync() -> None:
    """Test direct clients fetch metadata before deciding time sync support."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        request_mock = AsyncMock(
            return_value=json.loads(load_fixture("pps_device.json"))
        )
        bsblan._request = request_mock  # type: ignore[method-assign]

        with pytest.raises(BSBLANError, match=ErrorMsg.TIME_SYNC_NOT_SUPPORTED):
            await bsblan.set_time("01.01.2024 12:30:45")

    request_mock.assert_awaited_once_with(base_path="/JI")


@pytest.mark.asyncio
async def test_time_fetches_device_metadata_before_sync() -> None:
    """Test direct time reads fetch metadata before querying parameter 0."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        request_mock = AsyncMock(
            return_value=json.loads(load_fixture("pps_device.json"))
        )
        bsblan._request = request_mock  # type: ignore[method-assign]

        with pytest.raises(BSBLANError, match=ErrorMsg.TIME_SYNC_NOT_SUPPORTED):
            await bsblan.time()

    request_mock.assert_awaited_once_with(base_path="/JI")


@pytest.mark.asyncio
async def test_pps_state_uses_climate_params(pps_bsblan: BSBLAN) -> None:
    """Test PPS climate state reads use and normalize PPS parameter values."""
    request_mock = AsyncMock(return_value=json.loads(load_fixture("pps_state.json")))
    pps_bsblan._request = request_mock  # type: ignore[method-assign]

    state: State = await pps_bsblan.state()

    assert state.hvac_mode is not None
    assert state.hvac_mode.value == 1
    assert state.target_temperature is not None
    assert state.target_temperature.value == 20.5
    assert state.current_temperature is not None
    assert state.current_temperature.value == 19.5
    assert pps_bsblan.get_temperature_unit == "°C"
    assert [
        call.kwargs["params"]["Parameter"] for call in request_mock.await_args_list
    ] == ["15000,15004,15008", "15000,15004,15008"]


@pytest.mark.asyncio
async def test_pps_static_values_use_climate_bounds(pps_bsblan: BSBLAN) -> None:
    """Test PPS static values use frost and max setpoint parameters."""
    request_mock = AsyncMock(
        return_value=json.loads(load_fixture("pps_static_values.json"))
    )
    pps_bsblan._request = request_mock  # type: ignore[method-assign]

    static_values: StaticState = await pps_bsblan.static_values()

    assert static_values.min_temp is not None
    assert static_values.min_temp.value == 8.0
    assert static_values.max_temp is not None
    assert static_values.max_temp.value == 30.0
    assert [
        call.kwargs["params"]["Parameter"] for call in request_mock.await_args_list
    ] == ["15006,15007", "15006,15007"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hvac_mode", "expected_value"),
    [
        (0, "2"),
        (1, "0"),
        (3, "1"),
    ],
)
async def test_pps_thermostat_hvac_mode_writes_translated_value(
    pps_bsblan: BSBLAN,
    hvac_mode: int,
    expected_value: str,
) -> None:
    """Test PPS mode writes translate library modes to PPS raw values."""
    pps_bsblan._circuit_temp_ranges[1] = {"min": 8.0, "max": 30.0}
    pps_bsblan._circuit_temp_initialized.add(1)
    request_mock = AsyncMock(return_value={"status": "ok"})
    pps_bsblan._request = request_mock  # type: ignore[method-assign]

    await pps_bsblan.thermostat(hvac_mode=hvac_mode)

    request_mock.assert_awaited_with(
        base_path="/JS",
        data={"Parameter": "15000", "Value": expected_value, "Type": "1"},
    )


@pytest.mark.asyncio
async def test_pps_thermostat_temperature_writes_comfort_setpoint(
    pps_bsblan: BSBLAN,
) -> None:
    """Test PPS target temperature writes use comfort setpoint."""
    pps_bsblan._circuit_temp_ranges[1] = {"min": 8.0, "max": 30.0}
    pps_bsblan._circuit_temp_initialized.add(1)
    request_mock = AsyncMock(return_value={"status": "ok"})
    pps_bsblan._request = request_mock  # type: ignore[method-assign]

    await pps_bsblan.thermostat(target_temperature="20.5")

    request_mock.assert_awaited_with(
        base_path="/JS",
        data={"Parameter": "15004", "Value": "20.5", "Type": "1"},
    )


@pytest.mark.asyncio
async def test_pps_thermostat_rejects_cooling_temperature(
    pps_bsblan: BSBLAN,
) -> None:
    """Test PPS climate rejects cooling target writes."""
    pps_bsblan._circuit_temp_ranges[1] = {"min": 8.0, "max": 30.0}
    pps_bsblan._circuit_temp_initialized.add(1)
    request_mock = AsyncMock(return_value={"status": "ok"})
    pps_bsblan._request = request_mock  # type: ignore[method-assign]

    with pytest.raises(BSBLANInvalidParameterError, match="target_temperature_high"):
        await pps_bsblan.thermostat(target_temperature_high="24.0")

    request_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_pps_thermostat_rejects_unsupported_eco_mode(
    pps_bsblan: BSBLAN,
) -> None:
    """Test PPS climate rejects the library eco mode value."""
    pps_bsblan._circuit_temp_ranges[1] = {"min": 8.0, "max": 30.0}
    pps_bsblan._circuit_temp_initialized.add(1)
    request_mock = AsyncMock(return_value={"status": "ok"})
    pps_bsblan._request = request_mock  # type: ignore[method-assign]

    with pytest.raises(BSBLANInvalidParameterError):
        await pps_bsblan.thermostat(hvac_mode=2)

    request_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_pps_thermostat_rejects_read_only_bus() -> None:
    """Test PPS climate writes are blocked when the bus is read-only."""
    async with aiohttp.ClientSession() as session:
        bsblan = BSBLAN(BSBLANConfig(host="example.com"), session=session)
        bsblan._firmware_version = "5.1.0"
        bsblan._api_version = "v3"
        bsblan._device = Device(
            name="BSB-LAN",
            version="5.1.0",
            MAC="00:80:41:19:69:93",
            uptime=1,
            bus="PPS",
            buswritable=0,
        )
        bsblan._api_data = build_api_config("v3")
        bsblan._apply_bus_specific_api_config()
        bsblan._validator._api_validator = APIValidator(bsblan._api_data)
        request_mock = AsyncMock(return_value={"status": "ok"})
        bsblan._request = request_mock  # type: ignore[method-assign]

        with pytest.raises(BSBLANError, match=ErrorMsg.BUS_WRITE_NOT_SUPPORTED):
            await bsblan.thermostat(target_temperature="20.5")

    request_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_pps_circuit_discovery_returns_single_climate(
    pps_bsblan: BSBLAN,
) -> None:
    """Test PPS circuit discovery only probes and returns circuit 1."""
    request_mock = AsyncMock(
        return_value={"15000": {"value": "0", "unit": "", "desc": "Automatic"}}
    )
    pps_bsblan._request = request_mock  # type: ignore[method-assign]

    circuits = await pps_bsblan.get_available_circuits()

    assert circuits == [1]
    assert pps_bsblan._available_circuits == {1}
    request_mock.assert_awaited_once_with(params={"Parameter": "15000"})


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [{}, {"15000": {}}])
async def test_pps_circuit_discovery_returns_empty_without_mode(
    pps_bsblan: BSBLAN,
    response: dict[str, Any],
) -> None:
    """Test PPS circuit discovery handles missing operating mode data."""
    pps_bsblan._request = AsyncMock(return_value=response)  # type: ignore[method-assign]

    circuits = await pps_bsblan.get_available_circuits()

    assert circuits == []
    assert pps_bsblan._available_circuits == set()


@pytest.mark.asyncio
async def test_pps_circuit_discovery_returns_empty_on_error(
    pps_bsblan: BSBLAN,
) -> None:
    """Test PPS circuit discovery handles request errors."""
    pps_bsblan._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=BSBLANError("failed")
    )

    circuits = await pps_bsblan.get_available_circuits()

    assert circuits == []


@pytest.mark.asyncio
async def test_pps_rejects_second_circuit(pps_bsblan: BSBLAN) -> None:
    """Test PPS devices expose only one climate circuit."""
    with pytest.raises(BSBLANInvalidParameterError):
        await pps_bsblan.state(circuit=2)


def test_pps_normalization_ignores_missing_mode(pps_bsblan: BSBLAN) -> None:
    """Test PPS normalization tolerates partial or malformed responses."""
    pps_bsblan._normalize_pps_state_data({})
    pps_bsblan._normalize_pps_state_data({"hvac_mode": {"value": "unknown"}})
