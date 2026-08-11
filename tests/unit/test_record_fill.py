"""Tests for record_fill wiring and daily limit enforcement."""
from unittest import mock

import pytest

from cudaquant.data.schemas import Order, OrderSide, OrderType
from cudaquant.execution.order_service import OrderService
from cudaquant.risk.governor import RiskGovernor


@pytest.fixture
def mock_broker():
    b = mock.MagicMock()
    b.is_connected = True
    b.submit_order.return_value = "test-order-id"
    b.get_account.return_value = mock.MagicMock(cash=100000.0, portfolio_value=100000.0)
    b.get_positions.return_value = []
    return b


class TestRecordFill:
    """Prove record_fill() is called on every successful order."""

    def test_single_order_increments_daily_trades(self, mock_broker, monkeypatch):
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_paper_settings())
        governor = RiskGovernor({"max_daily_trades": 100})
        svc = OrderService(broker=mock_broker, governor=governor)
        assert governor._daily_trades == 0

        order = Order(symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.MARKET, qty=1)
        ok, msg, oid = svc.submit_order(order)
        assert ok, f"Expected success: {msg}"
        assert governor._daily_trades == 1

    def test_three_orders_increment_counter(self, mock_broker, monkeypatch):
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_paper_settings())
        governor = RiskGovernor({"max_daily_trades": 100})
        svc = OrderService(broker=mock_broker, governor=governor)

        order = Order(symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.MARKET, qty=1)
        for _i in range(3):
            ok, _, _ = svc.submit_order(order)
            assert ok
        assert governor._daily_trades == 3, f"Expected 3, got {governor._daily_trades}"


class TestDailyLimitEnforcement:
    """Prove daily limit blocks orders past threshold."""

    def test_limit_blocks_past_threshold(self, mock_broker, monkeypatch):
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_paper_settings())
        governor = RiskGovernor({"max_daily_trades": 2})
        svc = OrderService(broker=mock_broker, governor=governor)

        order = Order(symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.MARKET, qty=1)
        # First two pass
        assert svc.submit_order(order)[0]
        assert svc.submit_order(order)[0]
        # Third is blocked
        ok, msg, _ = svc.submit_order(order)
        assert not ok, f"Expected rejection, got: {msg}"
        assert "daily" in msg.lower() or "trade" in msg.lower()
        assert governor._daily_trades == 2  # Counter stops at limit


def _make_paper_settings():
    s = mock.MagicMock()
    s.TRADING_MODE = "paper"
    s.ENABLE_LIVE_TRADING = False
    s.live_trading_enabled = False
    s.CUDA_ENABLED = True
    s.MAX_POSITION_NOTIONAL = 100_000.0
    s.MAX_TOTAL_EXPOSURE = 500_000.0
    s.MAX_DAILY_TRADES = 50
    s.MAX_DAILY_LOSS = 5_000.0
    s.MAX_DRAWDOWN_PCT = 20.0
    s.KILL_SWITCH_FILE = "./.kill_switch"
    return s
