"""Safety tests for order execution — config, RiskGovernor, and KillSwitch gates.

ALL Alpaca HTTP calls are mocked — no real API keys needed.
These tests prove that each gate independently blocks order submission.
"""

import os
from unittest import mock

import pytest

from cudaquant.config.settings import Settings
from cudaquant.data.schemas import Order, OrderSide, OrderType
from cudaquant.execution.order_service import OrderService
from cudaquant.risk.governor import RiskGovernor
from cudaquant.risk.kill_switch import KillSwitch


@pytest.fixture
def mock_broker():
    """Mock AlpacaBroker — always returns success for submit_order."""
    broker = mock.MagicMock()
    broker.is_connected = True
    broker.submit_order.return_value = "test-order-123"
    broker.get_account.return_value = mock.MagicMock(
        cash=100000.0,
        portfolio_value=100000.0,
        buying_power=200000.0,
    )
    broker.get_positions.return_value = []
    return broker


@pytest.fixture
def valid_order():
    return Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        qty=10,
        limit_price=150.0,
    )


@pytest.fixture
def permissive_governor():
    """RiskGovernor that approves everything."""
    return RiskGovernor({
        "max_position_notional": 1_000_000,
        "max_total_exposure": 10_000_000,
        "max_daily_trades": 1000,
        "max_daily_loss": 1_000_000,
        "max_drawdown_pct": 100,
    })


class TestOrderServiceGates:
    """Each test proves a specific gate independently blocks submission."""

    def test_valid_order_passes_all_gates(
        self, mock_broker, valid_order, permissive_governor, monkeypatch,
    ):
        """With all gates open, a valid order succeeds."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        ks = KillSwitch("/tmp/test_killswitch_nonexistent")
        service = OrderService(broker=mock_broker, governor=permissive_governor, kill_switch=ks)

        ok, msg, order_id = service.submit_order(valid_order)
        assert ok, f"Expected success, got: {msg}"
        assert order_id == "test-order-123"
        mock_broker.submit_order.assert_called_once()

    # ── Gate 1: Config ──────────────────────────────────────────────────

    def test_gate1_invalid_trading_mode_rejected(
        self, mock_broker, valid_order, permissive_governor, monkeypatch,
    ):
        """TRADING_MODE='bogus' → rejected."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="bogus", ENABLE_LIVE_TRADING=False))

        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=KillSwitch("/tmp/nonexistent"))
        ok, msg, _ = service.submit_order(valid_order)
        assert not ok
        assert "invalid TRADING_MODE" in msg
        mock_broker.submit_order.assert_not_called()

    def test_gate1_live_mode_without_ack_rejected(
        self, mock_broker, valid_order, permissive_governor, monkeypatch,
    ):
        """TRADING_MODE='live' + ENABLE_LIVE_TRADING=False → rejected."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="live", ENABLE_LIVE_TRADING=False))

        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=KillSwitch("/tmp/nonexistent"))
        ok, msg, _ = service.submit_order(valid_order)
        assert not ok
        assert "live trading not enabled" in msg
        mock_broker.submit_order.assert_not_called()

    def test_gate1_paper_mode_with_live_ack_rejected(
        self, mock_broker, valid_order, permissive_governor, monkeypatch,
    ):
        """TRADING_MODE='paper' + ENABLE_LIVE_TRADING=True → inconsistent config."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=True))

        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=KillSwitch("/tmp/nonexistent"))
        ok, msg, _ = service.submit_order(valid_order)
        assert not ok
        assert "inconsistent config" in msg
        mock_broker.submit_order.assert_not_called()

    # ── Gate 2: RiskGovernor ────────────────────────────────────────────

    def test_gate2_risk_governor_rejects(
        self, mock_broker, valid_order, monkeypatch,
    ):
        """RiskGovernor rejection → order blocked before reaching broker."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        # Strict governor: max position notional = $100
        strict = RiskGovernor({"max_position_notional": 100})
        service = OrderService(broker=mock_broker, governor=strict,
                               kill_switch=KillSwitch("/tmp/nonexistent"))

        # Order for 10 shares of AAPL (~$150 each = $1500) exceeds $100 limit
        order = Order(symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.LIMIT, qty=10, limit_price=150.0)
        ok, msg, _ = service.submit_order(order)
        assert not ok
        assert "risk governor" in msg.lower()
        mock_broker.submit_order.assert_not_called()

    # ── Gate 3: KillSwitch ──────────────────────────────────────────────

    def test_gate3_kill_switch_blocks(
        self, mock_broker, valid_order, permissive_governor, monkeypatch,
    ):
        """Kill switch engaged → order rejected before reaching broker."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        ks = KillSwitch("/tmp/test_killswitch_gate3")
        ks.engage("test gate 3")

        try:
            service = OrderService(broker=mock_broker, governor=permissive_governor, kill_switch=ks)
            ok, msg, _ = service.submit_order(valid_order)
            assert not ok
            assert "kill switch" in msg.lower()
            mock_broker.submit_order.assert_not_called()
        finally:
            ks.disengage()

    def test_gate3_kill_switch_disengaged_allows_order(
        self, mock_broker, valid_order, permissive_governor, monkeypatch,
    ):
        """Kill switch NOT engaged → order proceeds (other gates pass)."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        ks = KillSwitch("/tmp/test_killswitch_disengaged")
        ks.disengage()

        service = OrderService(broker=mock_broker, governor=permissive_governor, kill_switch=ks)
        ok, msg, _ = service.submit_order(valid_order)
        assert ok, f"Expected success, got: {msg}"
        mock_broker.submit_order.assert_called_once()

    # ── Integration: all three gates ordered correctly ──────────────────

    def test_gates_run_in_order_config_first(
        self, mock_broker, valid_order, permissive_governor, monkeypatch,
    ):
        """Config gate is checked first — invalid mode prevents broker call."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="bogus", ENABLE_LIVE_TRADING=False))

        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=KillSwitch("/tmp/nonexistent"))
        ok, msg, _ = service.submit_order(valid_order)
        assert not ok
        # Broker should NEVER be called when config is invalid
        mock_broker.submit_order.assert_not_called()
        mock_broker.get_account.assert_not_called()


def _make_settings(**overrides):
    """Create a Settings-like object with given overrides."""
    s = mock.MagicMock(spec=Settings)
    s.TRADING_MODE = "paper"
    s.ENABLE_LIVE_TRADING = False
    s.CUDA_ENABLED = True
    s.live_trading_enabled = False
    s.MAX_POSITION_NOTIONAL = 100_000.0
    s.MAX_TOTAL_EXPOSURE = 500_000.0
    s.MAX_DAILY_TRADES = 50
    s.MAX_DAILY_LOSS = 5_000.0
    s.MAX_DRAWDOWN_PCT = 20.0
    s.KILL_SWITCH_FILE = "./.kill_switch"
    s.ALPACA_API_KEY = None
    s.ALPACA_SECRET_KEY = None
    s.ALPACA_PAPER = True

    for key, value in overrides.items():
        setattr(s, key, value)
        if key == "TRADING_MODE":
            s.live_trading_enabled = (overrides.get("TRADING_MODE") == "live"
                                      and overrides.get("ENABLE_LIVE_TRADING", False))

    return s
