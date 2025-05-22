"""Tests for BSBLAN authentication."""

# file deepcode ignore W0212: this is a testfile
# pylint: disable=protected-access

from aiohttp.helpers import BasicAuth

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig


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
    config.password = "testpassword"

    bsblan = BSBLAN(config)
    auth = bsblan._get_auth()

    assert isinstance(auth, BasicAuth)
    assert auth.login == "testuser"
    assert auth.password == "testpassword"
