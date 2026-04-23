"""Tests for heating_schedule method."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from bsblan.exceptions import BSBLANError
from bsblan.models import HeatingTimeSwitchPrograms

if TYPE_CHECKING:
    from bsblan import BSBLAN


def _build_schedule_fixture(param_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Build fixture data for schedule parameter IDs."""
    fixture: dict[str, dict[str, Any]] = {}
    for param_id in param_ids:
        if param_id in {"516", "536"}:
            fixture[param_id] = {
                "name": "Standard values",
                "value": "0",
                "unit": "",
                "desc": "No",
                "dataType": 1,
            }
        else:
            fixture[param_id] = {
                "name": f"Time switch {param_id}",
                "value": "06:00-22:00 ##:##-##:## ##:##-##:##",
                "unit": "",
                "desc": "",
                "dataType": 9,
            }
    return fixture


@pytest.mark.asyncio
async def test_heating_schedule_circuit1(mock_bsblan: BSBLAN) -> None:
    """Test reading heating schedule for circuit 1."""
    fixture_data = _build_schedule_fixture(
        ["501", "502", "503", "504", "505", "506", "507", "516"]
    )

    def mock_request(**kwargs: Any) -> dict[str, Any]:
        param_string = kwargs.get("params", {}).get("Parameter", "")
        requested_param_ids = param_string.split(",") if param_string else []
        return {
            param_id: fixture_data[param_id]
            for param_id in requested_param_ids
            if param_id in fixture_data
        }

    request_mock = AsyncMock(side_effect=mock_request)
    mock_bsblan._request = request_mock  # type: ignore[method-assign]

    result = await mock_bsblan.heating_schedule(circuit=1)

    assert isinstance(result, HeatingTimeSwitchPrograms)
    assert result.monday is not None
    assert result.monday.value == "06:00-22:00 ##:##-##:## ##:##-##:##"
    assert result.standard_values is not None
    assert result.standard_values.value == 0


@pytest.mark.asyncio
async def test_heating_schedule_circuit2(mock_bsblan: BSBLAN) -> None:
    """Test reading heating schedule for circuit 2."""
    fixture_data = _build_schedule_fixture(
        ["521", "522", "523", "524", "525", "526", "527", "536"]
    )

    def mock_request(**kwargs: Any) -> dict[str, Any]:
        param_string = kwargs.get("params", {}).get("Parameter", "")
        requested_param_ids = param_string.split(",") if param_string else []
        return {
            param_id: fixture_data[param_id]
            for param_id in requested_param_ids
            if param_id in fixture_data
        }

    request_mock = AsyncMock(side_effect=mock_request)
    mock_bsblan._request = request_mock  # type: ignore[method-assign]

    result = await mock_bsblan.heating_schedule(circuit=2)

    assert isinstance(result, HeatingTimeSwitchPrograms)
    assert result.monday is not None
    assert result.standard_values is not None


@pytest.mark.asyncio
async def test_heating_schedule_include_filter(mock_bsblan: BSBLAN) -> None:
    """Test include filter for heating schedule."""
    fixture_data = _build_schedule_fixture(["521", "536"])

    def mock_request(**kwargs: Any) -> dict[str, Any]:
        param_string = kwargs.get("params", {}).get("Parameter", "")
        requested_param_ids = param_string.split(",") if param_string else []
        return {
            param_id: fixture_data[param_id]
            for param_id in requested_param_ids
            if param_id in fixture_data
        }

    request_mock = AsyncMock(side_effect=mock_request)
    mock_bsblan._request = request_mock  # type: ignore[method-assign]

    result = await mock_bsblan.heating_schedule(
        include=["monday", "standard_values"],
        circuit=2,
    )

    assert result.monday is not None
    assert result.standard_values is not None
    assert result.tuesday is None

    call_args = request_mock.call_args
    assert call_args is not None
    assert call_args.kwargs["params"]["Parameter"] == "521,536"


@pytest.mark.asyncio
async def test_heating_schedule_empty_include_raises(mock_bsblan: BSBLAN) -> None:
    """Test empty include list raises error."""
    with pytest.raises(BSBLANError, match="Empty include list"):
        await mock_bsblan.heating_schedule(include=[], circuit=1)


@pytest.mark.asyncio
async def test_heating_schedule_invalid_include_raises(mock_bsblan: BSBLAN) -> None:
    """Test invalid include parameter raises error."""
    with pytest.raises(BSBLANError, match="None of the requested parameters"):
        await mock_bsblan.heating_schedule(include=["invalid_day"], circuit=1)


@pytest.mark.asyncio
async def test_heating_schedule_no_params_raises(mock_bsblan: BSBLAN) -> None:
    """Test no schedule params in response raises error."""
    mock_bsblan._request = AsyncMock(return_value={})  # type: ignore[method-assign]

    with pytest.raises(BSBLANError, match="No heating schedule parameters available"):
        await mock_bsblan.heating_schedule(circuit=1)
