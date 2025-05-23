"""Tests for BSBLAN configuration methods."""

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access

import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.constants import MULTI_PARAMETER_ERROR_MSG
from bsblan.exceptions import BSBLANError


def test_build_url() -> None:
    """Test the _build_url method."""
    # Test without passkey
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)
    url = bsblan._build_url("/JQ")
    assert str(url) == "http://example.com/JQ"

    # Test with passkey
    config_with_passkey = BSBLANConfig(host="example.com", passkey="1234")
    bsblan_with_passkey = BSBLAN(config_with_passkey)
    url_with_passkey = bsblan_with_passkey._build_url("/JQ")
    assert str(url_with_passkey) == "http://example.com/1234/JQ"

    # Test with custom port
    config_with_port = BSBLANConfig(host="example.com", port=8080)
    bsblan_with_port = BSBLAN(config_with_port)
    url_with_port = bsblan_with_port._build_url("/JQ")
    assert str(url_with_port) == "http://example.com:8080/JQ"


def test_get_headers() -> None:
    """Test the _get_headers method."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Test with firmware version not set (default)
    headers = bsblan._get_headers()
    assert "User-Agent" in headers
    assert "PythonBSBLAN/None" in headers["User-Agent"]
    assert "Accept" in headers
    assert headers["Accept"] == "application/json, */*"

    # Test with firmware version set
    bsblan._firmware_version = "1.0.38"
    headers_with_version = bsblan._get_headers()
    assert "PythonBSBLAN/1.0.38" in headers_with_version["User-Agent"]


def test_validate_single_parameter() -> None:
    """Test the _validate_single_parameter method."""
    config = BSBLANConfig(host="example.com")
    bsblan = BSBLAN(config)

    # Test with exactly one parameter
    bsblan._validate_single_parameter(1, None, None, error_msg="Test error")

    # Test with no parameters
    with pytest.raises(BSBLANError, match=MULTI_PARAMETER_ERROR_MSG):
        bsblan._validate_single_parameter(
            None, None, None, error_msg=MULTI_PARAMETER_ERROR_MSG
        )

    # Test with multiple parameters
    with pytest.raises(BSBLANError, match=MULTI_PARAMETER_ERROR_MSG):
        bsblan._validate_single_parameter(
            1, 2, None, error_msg=MULTI_PARAMETER_ERROR_MSG
        )

    # Test with all parameters
    with pytest.raises(BSBLANError, match=MULTI_PARAMETER_ERROR_MSG):
        bsblan._validate_single_parameter(1, 2, 3, error_msg=MULTI_PARAMETER_ERROR_MSG)
