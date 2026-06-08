"""Tests for API version and firmware version error handling."""
# pylint: disable=protected-access

from unittest.mock import AsyncMock, patch

import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import ErrorMsg
from bsblan.exceptions import BSBLANError, BSBLANVersionError
from bsblan.models import Device


@pytest.mark.asyncio
async def test_resolve_api_capabilities_without_json_api() -> None:
    """Test that a missing JSON-API version raises BSBLANVersionError."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # No JSON-API version available (device did not expose /JV).
    with pytest.raises(BSBLANVersionError):
        bsblan._resolve_api_capabilities()


@pytest.mark.asyncio
async def test_resolve_api_capabilities_ignores_firmware() -> None:
    """Test the firmware version is not used to select the configuration.

    Even a modern firmware version cannot stand in for a missing JSON-API
    version: without /JV the device capabilities cannot be confirmed.
    """
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Firmware is retrieved for information only; it must not gate support.
    bsblan._firmware_version = "5.0.16"

    with pytest.raises(BSBLANVersionError):
        bsblan._resolve_api_capabilities()


@pytest.mark.asyncio
async def test_fetch_firmware_version() -> None:
    """Test fetching firmware version from device."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Create mock device with test version
    device = Device(
        name="Test Device", version="3.1.0", MAC="00:11:22:33:44:55", uptime=1000
    )

    # Mock device method to return our test device
    with (
        patch.object(bsblan, "device", AsyncMock(return_value=device)),
        patch.object(bsblan, "_fetch_json_api_version", AsyncMock()),
        patch.object(bsblan, "_resolve_api_capabilities"),
    ):
        await bsblan._fetch_firmware_version()

        # Verify firmware version was set
        assert bsblan._firmware_version == "3.1.0"


@pytest.mark.asyncio
async def test_setup_api_validator_no_api_version() -> None:
    """Test setup API validator with no API version set."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Force the capability flag to None to test the defensive error path
    bsblan._supports_full_config = None

    with pytest.raises(BSBLANError, match=ErrorMsg.API_VERSION):
        await bsblan._setup_api_validator()


@pytest.mark.asyncio
async def test_process_response_v5_payload_removal() -> None:
    """Test that BSB-LAN 5.x payload field is removed from responses."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to 5.0.16
    bsblan._firmware_version = "5.0.16"

    # Mock response with payload field (as added in BSB-LAN 5.0+)
    response_with_payload = {
        "8700": {"value": "20.5", "unit": "°C"},
        "8740": {"value": "21.0", "unit": "°C"},
        "payload": "debug_payload_data_here",
    }

    # Process the response
    processed = bsblan._transport._process_response(response_with_payload, "/JQ")

    # Payload should be removed
    expected = {
        "8700": {"value": "20.5", "unit": "°C"},
        "8740": {"value": "21.0", "unit": "°C"},
    }

    assert processed == expected
    assert "payload" not in processed


@pytest.mark.asyncio
async def test_process_response_non_jq_endpoint() -> None:
    """Test that non-JQ endpoints are not processed for payload removal."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to 5.0.16
    bsblan._firmware_version = "5.0.16"

    # Mock response with payload field
    response_with_payload = {
        "name": "BSB-LAN",
        "version": "5.0.16",
        "payload": "should_remain_for_non_jq",
    }

    # Process the response for non-JQ endpoint
    processed = bsblan._transport._process_response(response_with_payload, "/JI")

    # Payload should remain for non-JQ endpoints
    assert processed == response_with_payload
    assert "payload" in processed


@pytest.mark.asyncio
async def test_json_api_version_enables_full_config() -> None:
    """Test JSON-API version >= 2.0 enables the full config."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "2.0"
    bsblan._resolve_api_capabilities()

    assert bsblan._supports_full_config is True


@pytest.mark.asyncio
async def test_json_api_version_uses_basic_config() -> None:
    """Test JSON-API version in [1.0, 2.0) uses the basic config."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "1.5"
    bsblan._resolve_api_capabilities()

    assert bsblan._supports_full_config is False


@pytest.mark.asyncio
async def test_json_api_version_unsupported() -> None:
    """Test JSON-API version below the supported floor raises."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "0.9"

    with pytest.raises(BSBLANVersionError):
        bsblan._resolve_api_capabilities()


@pytest.mark.asyncio
async def test_json_api_version_invalid_string() -> None:
    """Test a non-PEP440 JSON-API version raises BSBLANVersionError."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "not-a-version"

    with pytest.raises(BSBLANVersionError):
        bsblan._resolve_api_capabilities()


@pytest.mark.asyncio
async def test_json_api_version_used_regardless_of_firmware() -> None:
    """Test the JSON-API version alone selects the config, ignoring firmware."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Firmware is informational only; the JSON-API version drives the result.
    bsblan._firmware_version = "1.0.0"
    bsblan._json_api_version = "2.0"
    bsblan._resolve_api_capabilities()

    assert bsblan._supports_full_config is True


@pytest.mark.asyncio
async def test_json_api_version_property() -> None:
    """Test the public json_api_version property exposes the /JV version."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Defaults to None until /JV is fetched.
    assert bsblan.json_api_version is None

    bsblan._json_api_version = "2.0"
    assert bsblan.json_api_version == "2.0"


@pytest.mark.asyncio
async def test_version_error_exposes_version() -> None:
    """Test BSBLANVersionError stores the unsupported version on the exception."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "0.9"

    with pytest.raises(BSBLANVersionError) as exc_info:
        bsblan._resolve_api_capabilities()

    assert exc_info.value.version == "0.9"


@pytest.mark.asyncio
async def test_fetch_json_api_version_success() -> None:
    """Test fetching the JSON-API version from the /JV endpoint."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    with patch.object(
        bsblan, "_request", AsyncMock(return_value={"api_version": "2.0"})
    ) as mock_request:
        await bsblan._fetch_json_api_version()

    assert bsblan._json_api_version == "2.0"
    mock_request.assert_awaited_once_with(base_path="/JV")


@pytest.mark.asyncio
async def test_fetch_json_api_version_falls_back_on_error() -> None:
    """Test a missing /JV endpoint leaves the JSON-API version unset."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    with patch.object(bsblan, "_request", AsyncMock(side_effect=BSBLANError("404"))):
        await bsblan._fetch_json_api_version()

    assert bsblan._json_api_version is None


@pytest.mark.asyncio
async def test_fetch_json_api_version_falls_back_on_malformed_payload() -> None:
    """Test a malformed /JV payload leaves the JSON-API version unset."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    with patch.object(
        bsblan, "_request", AsyncMock(return_value={"unexpected": "data"})
    ):
        await bsblan._fetch_json_api_version()

    assert bsblan._json_api_version is None


@pytest.mark.asyncio
async def test_fetch_json_api_version_cached() -> None:
    """Test the JSON-API version is not re-fetched when already known."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "2.0"

    with patch.object(bsblan, "_request", AsyncMock()) as mock_request:
        await bsblan._fetch_json_api_version()

    mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_firmware_version_queries_json_api() -> None:
    """Test firmware fetch also fetches the JSON-API version."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    device = Device(
        name="Test Device", version="2.2.3", MAC="00:11:22:33:44:55", uptime=1000
    )

    with (
        patch.object(bsblan, "device", AsyncMock(return_value=device)),
        patch.object(
            bsblan, "_request", AsyncMock(return_value={"api_version": "2.0"})
        ),
    ):
        await bsblan._fetch_firmware_version()

    assert bsblan._firmware_version == "2.2.3"
    assert bsblan._json_api_version == "2.0"
    # The JSON-API version drives the result; firmware is informational only.
    assert bsblan._supports_full_config is True
