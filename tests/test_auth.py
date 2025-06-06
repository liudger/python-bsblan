"""Tests for BSBLAN authentication."""

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access

from aiohttp.helpers import BasicAuth

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig
from bsblan.exceptions import BSBLANAuthError


def test_get_auth_without_credentials() -> None:
    """Test the _get_auth method without credentials."""
    config_no_auth = BSBLANConfig(host="example.com")
    bsblan_no_auth = BSBLAN(config_no_auth)
    auth = bsblan_no_auth._get_auth()
    assert auth is None


def test_get_auth_with_credentials() -> None:
    """Test the _get_auth method with credentials."""
    # Create config with username and password
    config = BSBLANConfig(host="example.com")
    config.username = "testuser"
    config.password = "testpassword"  # noqa: S105

    bsblan = BSBLAN(config)
    auth = bsblan._get_auth()

    assert isinstance(auth, BasicAuth)
    assert auth.login == "testuser"
    assert auth.password == "testpassword"  # noqa: S105


def test_bsblan_auth_error_default_message() -> None:
    """Test BSBLANAuthError default message."""
    error = BSBLANAuthError()
    assert (
        error.message
        == "Authentication failed. Please check your username and password."
    )
    assert (
        str(error) == "Authentication failed. Please check your username and password."
    )


def test_bsblan_auth_error_custom_message() -> None:
    """Test BSBLANAuthError with custom message."""
    custom_message = "Invalid credentials provided"
    error = BSBLANAuthError(custom_message)
    assert error.message == custom_message
    assert str(error) == custom_message
