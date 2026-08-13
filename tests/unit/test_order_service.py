"""Safety tests for order execution — config, RiskGovernor, and KillSwitch gates.

ALL Alpaca HTTP calls are mocked — no real API keys needed.
These tests prove that each gate independently blocks order submission.
"""

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
        """TRADING_MODE='live' + no .env acknowledgement → rejected."""
        monkeypatch.delenv("ENABLE_LIVE_TRADING", raising=False)
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="live", ENABLE_LIVE_TRADING=False))

        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=KillSwitch("/tmp/nonexistent"))
        ok, msg, _ = service.submit_order(valid_order)
        assert not ok
        assert "live trading not enabled" in msg
        mock_broker.submit_order.assert_not_called()

    def test_gate1_paper_mode_allowed_even_with_live_ack(
        self, mock_broker, valid_order, permissive_governor, monkeypatch,
    ):
        """Paper mode must work regardless of the .env acknowledgement.

        Regression guard for the runtime-toggle design: the old env-only
        check rejected paper orders whenever ENABLE_LIVE_TRADING was set,
        which would have made paper trading impossible after acknowledging
        live trading in .env.
        """
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=True))

        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=KillSwitch("/tmp/nonexistent"))
        ok, msg, _ = service.submit_order(valid_order)
        assert ok, f"Paper mode must allow orders with ack set, got: {msg}"
        mock_broker.submit_order.assert_called_once()

    def test_gate1_live_mode_with_env_ack_allows(
        self, mock_broker, valid_order, permissive_governor, monkeypatch,
    ):
        """Live mode + real .env acknowledgement in the process environment → allowed."""
        monkeypatch.setenv("ENABLE_LIVE_TRADING", "I_UNDERSTAND_LIVE_TRADING_RISK")
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="live", ENABLE_LIVE_TRADING=True))

        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=KillSwitch("/tmp/nonexistent"))
        ok, msg, _ = service.submit_order(valid_order)
        assert ok, f"Live mode with env ack should pass gate 1, got: {msg}"
        mock_broker.submit_order.assert_called_once()

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

    def test_market_order_default_path_runs_all_gates(
        self, mock_broker, permissive_governor, monkeypatch,
    ):
        """A MARKET order with no limit_price (the API default path) runs all 3 gates.

        This is the regression test for Part 1 bug #1: the old code crashed
        with NameError because ref_price referenced unassigned variables.
        """
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        ks = KillSwitch("/tmp/test_market_order_ks")
        ks.disengage()

        order = Order(symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.MARKET, qty=1)

        service = OrderService(broker=mock_broker, governor=permissive_governor, kill_switch=ks)
        ok, msg, order_id = service.submit_order(order)
        assert ok, f"Market order should pass all gates, got: {msg}"
        assert order_id is not None
        # Prove broker.submit_order was actually called — all gates passed
        mock_broker.submit_order.assert_called_once()

    def test_market_order_with_unspecified_params(
        self, mock_broker, permissive_governor, monkeypatch,
    ):
        """Market order with ONLY symbol/side/qty (no limit_price) runs all gates.

        Regression for the Part 1 bug where an unset limit_price crashed with
        NameError before any gate ran. `order_type` is schema-required (the
        route layer supplies the "market" default), so the unspecified param
        here is `limit_price` — the field whose None default hit the bug.
        """
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        ks = KillSwitch("/tmp/test_market_order_unspecified")
        ks.disengage()

        order = Order(symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.MARKET, qty=1)

        service = OrderService(broker=mock_broker, governor=permissive_governor, kill_switch=ks)
        ok, msg, order_id = service.submit_order(order)
        assert ok, f"Market order should pass all gates, got: {msg}"
        assert order_id is not None
        # All 3 gates ran without crashing: account/positions fetched for the
        # risk check, governor approved, kill switch checked, order submitted.
        mock_broker.get_account.assert_called()
        mock_broker.get_positions.assert_called()
        mock_broker.submit_order.assert_called_once()

    def test_order_service_with_fractional_qty(
        self, mock_broker, permissive_governor, monkeypatch,
    ):
        """Fractional qty (crypto-style 0.0234 BTC) submits successfully.

        Order.qty is declared ``float`` in cudaquant.data.schemas, so
        fractional-share / crypto order quantities pass the schema and flow
        through all three gates to the broker unchanged.
        """
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        ks = KillSwitch("/tmp/test_fractional_qty_ks")
        ks.disengage()

        order = Order(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=0.0234,
        )
        service = OrderService(broker=mock_broker, governor=permissive_governor, kill_switch=ks)

        ok, msg, order_id = service.submit_order(order)
        assert ok, f"Expected success, got: {msg}"
        assert order_id == "test-order-123"
        mock_broker.submit_order.assert_called_once()
        submitted = mock_broker.submit_order.call_args[0][0]
        assert submitted.qty == 0.0234


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
