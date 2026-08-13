"""Hermetic tests for AlpacaBroker connection handling.

The constructor must NEVER make network calls (alpaca-py has no request
timeout — a sync verify at import/boot could hang the app forever when the
network is unreachable). Verification must be lazy, cached, and bounded by a
thread join timeout. No real API keys or network are used here — TradingClient
is monkeypatched.
"""

import threading
from unittest import mock

import pytest

from cudaquant.config.settings import Settings
from cudaquant.providers.alpaca_broker import AlpacaBroker


@pytest.fixture
def fake_creds(monkeypatch):
    """Point AlpacaBroker at monkeypatched settings with fake credentials."""
    monkeypatch.setattr(
        "cudaquant.providers.alpaca_broker.settings",
        mock.MagicMock(
            spec=Settings,
            ALPACA_API_KEY="pk_fake",
            ALPACA_SECRET_KEY="sk_fake",
            ALPACA_PAPER=True,
        ),
    )


def test_constructor_makes_no_network_calls(monkeypatch, fake_creds):
    """__init__ builds the SDK client but must not call any endpoint."""
    fake_client = mock.MagicMock()
    monkeypatch.setattr(
        "cudaquant.providers.alpaca_broker.TradingClient",
        lambda **kwargs: fake_client,
    )
    broker = AlpacaBroker()
    fake_client.get_account.assert_not_called()
    assert broker._connected is None  # unknown until first verification


def test_verify_connection_success_and_cached(monkeypatch, fake_creds):
    """A successful verification is cached — the SDK call happens once."""
    fake_client = mock.MagicMock()
    monkeypatch.setattr(
        "cudaquant.providers.alpaca_broker.TradingClient",
        lambda **kwargs: fake_client,
    )
    broker = AlpacaBroker()
    assert broker.verify_connection() is True
    assert broker.verify_connection() is True
    assert broker.is_connected is True
    fake_client.get_account.assert_called_once()


def test_verify_connection_bounded_when_network_hangs(monkeypatch, fake_creds):
    """A hanging SDK call must NOT hang verify_connection indefinitely —
    it returns False after ~verify_timeout (fail-closed)."""
    release = threading.Event()
    fake_client = mock.MagicMock()

    def hang_get_account():
        release.wait()  # block the daemon thread forever (simulated dead network)

    fake_client.get_account.side_effect = hang_get_account
    monkeypatch.setattr(
        "cudaquant.providers.alpaca_broker.TradingClient",
        lambda **kwargs: fake_client,
    )
    broker = AlpacaBroker(verify_timeout=0.3)
    assert broker.verify_connection() is False
    assert broker.is_connected is False
    release.set()  # let the daemon thread finish cleanly


def test_verify_connection_error_reports_false(monkeypatch, fake_creds):
    fake_client = mock.MagicMock()
    fake_client.get_account.side_effect = RuntimeError("auth failed")
    monkeypatch.setattr(
        "cudaquant.providers.alpaca_broker.TradingClient",
        lambda **kwargs: fake_client,
    )
    broker = AlpacaBroker()
    assert broker.verify_connection() is False


def test_verify_connection_failure_not_cached(monkeypatch, fake_creds):
    """A failed verification is retried on the next read — only success is
    cached, so a transient outage recovers without a broker rebuild."""
    fake_client = mock.MagicMock()
    fake_client.get_account.side_effect = RuntimeError("auth failed")
    monkeypatch.setattr(
        "cudaquant.providers.alpaca_broker.TradingClient",
        lambda **kwargs: fake_client,
    )
    broker = AlpacaBroker()
    assert broker.verify_connection() is False
    fake_client.get_account.side_effect = None  # network recovers
    assert broker.verify_connection() is True
    assert broker.is_connected is True


def test_no_credentials_never_verifies(monkeypatch):
    """No creds → disconnected immediately, no client, no network."""
    monkeypatch.setattr(
        "cudaquant.providers.alpaca_broker.settings",
        mock.MagicMock(
            spec=Settings,
            ALPACA_API_KEY=None,
            ALPACA_SECRET_KEY=None,
            ALPACA_PAPER=True,
        ),
    )
    monkeypatch.setattr(
        "cudaquant.providers.alpaca_broker.TradingClient",
        mock.MagicMock(side_effect=AssertionError("must not be constructed")),
    )
    broker = AlpacaBroker()
    assert broker.is_connected is False
    assert broker.verify_connection() is False
