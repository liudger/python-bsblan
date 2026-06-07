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
async def test_set_api_version_without_firmware() -> None:
    """Test setting API version with firmware version not set."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Firmware version is None by default
    with pytest.raises(BSBLANError, match=ErrorMsg.FIRMWARE_VERSION):
        bsblan._set_api_version()


@pytest.mark.asyncio
async def test_set_api_version_unsupported() -> None:
    """Test setting API version with unsupported firmware version."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version below the supported floor (< 2.0.0)
    bsblan._firmware_version = "1.9.0"

    with pytest.raises(BSBLANVersionError):
        bsblan._set_api_version()


@pytest.mark.asyncio
async def test_set_api_version_v2_basic() -> None:
    """Test legacy 2.x firmware maps to the basic v2 config."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._firmware_version = "2.2.3"
    bsblan._set_api_version()

    assert bsblan._api_version == "v2"


@pytest.mark.asyncio
async def test_set_api_version_rejects_legacy_firmware() -> None:
    """Test legacy firmware that previously mapped to v1 is unsupported."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to legacy v1-compatible firmware
    bsblan._firmware_version = "1.0.0"

    with pytest.raises(BSBLANVersionError):
        bsblan._set_api_version()


@pytest.mark.asyncio
async def test_set_api_version_invalid_firmware_string() -> None:
    """Test non-PEP440 firmware strings raise BSBLANVersionError."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Firmware strings with build metadata are not PEP 440 compliant
    bsblan._firmware_version = "1.0.38-not-a-version"

    with pytest.raises(BSBLANVersionError):
        bsblan._set_api_version()


@pytest.mark.asyncio
async def test_set_api_version_v3() -> None:
    """Test setting API version with v3 compatible firmware."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to v3 compatible
    bsblan._firmware_version = "3.0.0"
    bsblan._set_api_version()

    assert bsblan._api_version == "v3"


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
        patch.object(bsblan, "_set_api_version"),
    ):
        await bsblan._fetch_firmware_version()

        # Verify firmware version was set
        assert bsblan._firmware_version == "3.1.0"


@pytest.mark.asyncio
async def test_setup_api_validator_no_api_version() -> None:
    """Test setup API validator with no API version set."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Force API version to None to test the defensive error path
    bsblan._api_version = None

    with pytest.raises(BSBLANError, match=ErrorMsg.API_VERSION):
        await bsblan._setup_api_validator()


@pytest.mark.asyncio
async def test_set_api_version_v5() -> None:
    """Test setting API version with v5 compatible firmware (BSB-LAN 5.x)."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to 5.0.16 (current BSB-LAN version)
    bsblan._firmware_version = "5.0.16"
    bsblan._set_api_version()

    assert bsblan._api_version == "v3"


@pytest.mark.asyncio
async def test_set_api_version_v5_early() -> None:
    """Test setting API version with early v5 compatible firmware."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Set firmware version to 5.0.0 (first 5.x version)
    bsblan._firmware_version = "5.0.0"
    bsblan._set_api_version()

    assert bsblan._api_version == "v3"


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
async def test_set_api_version_v5_edge_cases() -> None:
    """Test edge cases for BSB-LAN 5.x version detection."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Test version 4.9.9 (should still be v3, not v5)
    bsblan._firmware_version = "4.9.9"
    bsblan._set_api_version()
    assert bsblan._api_version == "v3"

    # Test version 5.0.0-beta (should be v3)
    bsblan._firmware_version = "5.0.0"
    bsblan._set_api_version()
    assert bsblan._api_version == "v3"


@pytest.mark.asyncio
async def test_unsupported_version_still_fails() -> None:
    """Test that firmware below the supported floor (< 2.0.0) still fails."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Test that version 1.9.9 still fails
    bsblan._firmware_version = "1.9.9"

    with pytest.raises(BSBLANVersionError):
        bsblan._set_api_version()


@pytest.mark.asyncio
async def test_legacy_2x_maps_to_basic_v2() -> None:
    """Test that legacy 2.x firmware maps to the basic v2 config."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # 2.0.0 is the lower bound of basic support
    bsblan._firmware_version = "2.0.0"
    bsblan._set_api_version()
    assert bsblan._api_version == "v2"

    # 2.9.9 still maps to basic v2 (below the 3.0.0 v3 threshold)
    bsblan._firmware_version = "2.9.9"
    bsblan._set_api_version()
    assert bsblan._api_version == "v2"


@pytest.mark.asyncio
async def test_json_api_version_v3() -> None:
    """Test JSON-API version >= 2.0 maps to the full v3 config."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "2.0"
    bsblan._set_api_version()

    assert bsblan._api_version == "v3"


@pytest.mark.asyncio
async def test_json_api_version_basic_v2() -> None:
    """Test JSON-API version in [1.0, 2.0) maps to the basic v2 config."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "1.5"
    bsblan._set_api_version()

    assert bsblan._api_version == "v2"


@pytest.mark.asyncio
async def test_json_api_version_unsupported() -> None:
    """Test JSON-API version below the supported floor raises."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "0.9"

    with pytest.raises(BSBLANVersionError):
        bsblan._set_api_version()


@pytest.mark.asyncio
async def test_json_api_version_invalid_string() -> None:
    """Test a non-PEP440 JSON-API version raises BSBLANVersionError."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "not-a-version"

    with pytest.raises(BSBLANVersionError):
        bsblan._set_api_version()


@pytest.mark.asyncio
async def test_json_api_version_takes_precedence_over_firmware() -> None:
    """Test the JSON-API version is preferred over the firmware version."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Firmware would map to v2, but a modern JSON-API version wins.
    bsblan._firmware_version = "2.2.3"
    bsblan._json_api_version = "2.0"
    bsblan._set_api_version()

    assert bsblan._api_version == "v3"


@pytest.mark.asyncio
async def test_api_version_property() -> None:
    """Test the public api_version property reflects the resolved version."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    bsblan._json_api_version = "2.0"
    bsblan._set_api_version()

    assert bsblan.api_version == "v3"


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

    bsblan._firmware_version = "1.9.0"

    with pytest.raises(BSBLANVersionError) as exc_info:
        bsblan._set_api_version()

    assert exc_info.value.version == "1.9.0"


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
    # JSON-API version wins over the legacy firmware mapping.
    assert bsblan._api_version == "v3"
