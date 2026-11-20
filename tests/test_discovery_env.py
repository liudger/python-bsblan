"""Environment loading for example discovery helpers."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

import pytest

from tests.test_control_roundtrip import EXAMPLES

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def discovery_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import the discovery example module from examples/."""
    monkeypatch.syspath_prepend(str(EXAMPLES))
    return importlib.import_module("discovery")


def test_get_config_from_env_loads_dotenv_as_fallback(
    discovery_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing variables should trigger non-overriding .env loading when available."""
    for name in (
        discovery_module.ENV_BSBLAN_HOST,
        discovery_module.ENV_BSBLAN_PORT,
        discovery_module.ENV_BSBLAN_USER,
        discovery_module.ENV_BSBLAN_PASS,
        discovery_module.ENV_BSBLAN_PASSKEY,
    ):
        monkeypatch.delenv(name, raising=False)

    called: list[bool] = []

    def fake_fallback() -> None:
        called.append(True)
        monkeypatch.setenv(discovery_module.ENV_BSBLAN_HOST, "example.com")
        monkeypatch.setenv(discovery_module.ENV_BSBLAN_PORT, "8080")
        monkeypatch.setenv(discovery_module.ENV_BSBLAN_USER, "user")
        monkeypatch.setenv(discovery_module.ENV_BSBLAN_PASS, "pass")
        monkeypatch.setenv(discovery_module.ENV_BSBLAN_PASSKEY, "key")

    monkeypatch.setattr(discovery_module, "_load_dotenv_fallback", fake_fallback)

    result = discovery_module.get_config_from_env()

    assert called == [True]
    assert result == {
        "host": "example.com",
        "port": 8080,
        "username": "user",
        "password": "pass",
        "passkey": "key",
    }


def test_get_config_from_env_reads_real_dotenv_file(
    discovery_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The real dotenv loader should read a known file independent of cwd."""
    for name in (
        discovery_module.ENV_BSBLAN_HOST,
        discovery_module.ENV_BSBLAN_PORT,
        discovery_module.ENV_BSBLAN_USER,
        discovery_module.ENV_BSBLAN_PASS,
        discovery_module.ENV_BSBLAN_PASSKEY,
    ):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BSBLAN_HOST=example.com\n"
        "BSBLAN_PORT=8080\n"
        "BSBLAN_USER=file-user\n"
        "BSBLAN_PASS=file-pass\n"
        "BSBLAN_PASSKEY=file-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(discovery_module, "DOTENV_PATH", env_file, raising=False)

    result = discovery_module.get_config_from_env()

    assert result == {
        "host": "example.com",
        "port": 8080,
        "username": "file-user",
        "password": "file-pass",
        "passkey": "file-key",
    }


def test_get_config_from_env_skips_dotenv_when_all_values_present(
    discovery_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When all values are already set, dotenv fallback should not run."""
    monkeypatch.setenv(discovery_module.ENV_BSBLAN_HOST, "example.com")
    monkeypatch.setenv(discovery_module.ENV_BSBLAN_PORT, "80")
    monkeypatch.setenv(discovery_module.ENV_BSBLAN_USER, "user")
    monkeypatch.setenv(discovery_module.ENV_BSBLAN_PASS, "pass")
    monkeypatch.setenv(discovery_module.ENV_BSBLAN_PASSKEY, "")

    def fail_if_called() -> None:
        msg = "dotenv fallback should not be called"
        raise AssertionError(msg)

    monkeypatch.setattr(discovery_module, "_load_dotenv_fallback", fail_if_called)

    result = discovery_module.get_config_from_env()

    assert result == {
        "host": "example.com",
        "port": 80,
        "username": "user",
        "password": "pass",
        "passkey": "",
    }
