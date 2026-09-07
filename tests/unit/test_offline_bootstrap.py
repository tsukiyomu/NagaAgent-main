"""Contracts for the collection-time sandbox, independent of external services."""
from pathlib import Path
import socket

import dotenv
import pytest

from tests.support.offline_bootstrap import OfflineBootstrap

pytestmark = [pytest.mark.unit]


def test_offline_bootstrap_isolates_home_config_and_dotenv(monkeypatch, tmp_path):
    monkeypatch.setenv("NAGA_ENABLE_REAL_LLM_TESTS", "0")
    original_home = Path.home()
    bootstrap = OfflineBootstrap()
    try:
        bootstrap.install()
        assert Path.home() == Path(bootstrap.directory.name)
        assert Path.home() != original_home
        assert not (Path(__file__).resolve().parents[2] / "config.json").is_file()
        # Config precedence tests must still see their own fixture files normally.
        fixture_config = tmp_path / "config.json"
        fixture_config.touch()
        assert fixture_config.is_file()
        assert dotenv.load_dotenv() is False
    finally:
        bootstrap.close()
    assert Path.home() == original_home


@pytest.mark.parametrize("method", ["connect", "connect_ex", "create_connection"])
def test_offline_bootstrap_blocks_and_records_connections(monkeypatch, method):
    monkeypatch.setenv("NAGA_ENABLE_REAL_LLM_TESTS", "0")
    bootstrap = OfflineBootstrap()
    try:
        bootstrap.install()
        with pytest.raises(RuntimeError, match="external connection forbidden"):
            if method == "create_connection":
                socket.create_connection(("127.0.0.1", 9))
            else:
                with socket.socket() as sock:
                    getattr(sock, method)(("127.0.0.1", 9))
        assert bootstrap.attempts == ["('127.0.0.1', 9)"]
    finally:
        bootstrap.close()


def test_offline_bootstrap_allows_asyncio_private_socketpair(monkeypatch):
    monkeypatch.setenv("NAGA_ENABLE_REAL_LLM_TESTS", "0")
    bootstrap = OfflineBootstrap()
    try:
        bootstrap.install()
        first, second = socket.socketpair()
        first.close()
        second.close()
        assert bootstrap.attempts == []
    finally:
        bootstrap.close()
