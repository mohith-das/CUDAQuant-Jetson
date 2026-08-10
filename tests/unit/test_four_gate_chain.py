"""End-to-end safety tests for the full 4-gate execution chain.

Every champion-signal execution must pass ALL four gates before the broker
is touched:

  Gate 4: SCHEDULER_AUTO_EXECUTE          (SchedulerService.execute_champion_signal)
  Gate 1: TRADING_MODE / ENABLE_LIVE_TRADING  (OrderService.submit_order)
  Gate 2: RiskGovernor.pre_trade_check()      (OrderService.submit_order)
  Gate 3: KillSwitch.is_engaged()             (OrderService.submit_order)

These tests prove the gates chain correctly: each gate independently blocks,
and opening gate 4 never bypasses gates 1-3. ALL broker calls are mocked —
no real API keys or network needed.
"""

from unittest import mock

import pytest

from cudaquant.config.settings import Settings
from cudaquant.data.schemas import OrderSide
from cudaquant.execution.order_service import OrderService
from cudaquant.risk.governor import RiskGovernor
from cudaquant.risk.kill_switch import KillSwitch
from cudaquant.scheduler.service import SchedulerService


@pytest.fixture
def mock_broker():
    """Mock AlpacaBroker — always returns success for submit_order."""
    broker = mock.MagicMock()
    broker.is_connected = True
    broker.submit_order.return_value = "test-id"
    broker.get_account.return_value = mock.MagicMock(
        cash=100000.0,
        portfolio_value=100000.0,
        buying_power=200000.0,
    )
    broker.get_positions.return_value = []
    return broker


@pytest.fixture
def permissive_governor(tmp_path):
    """RiskGovernor that approves everything (own kill switch at tmp path)."""
    return RiskGovernor({
        "max_position_notional": 1_000_000,
        "max_total_exposure": 10_000_000,
        "max_daily_trades": 1000,
        "max_daily_loss": 1_000_000,
        "max_drawdown_pct": 100,
        "kill_switch_file": str(tmp_path / "governor_kill_switch"),
    })


@pytest.fixture
def champion_signal():
    """A champion's signal dict: {"symbol", "side", "qty"}."""
    return {"symbol": "AAPL", "side": "buy", "qty": 5}


def _disengaged_kill_switch(tmp_path):
    """Fresh, disengaged kill switch for a test's tmp dir."""
    ks = KillSwitch(str(tmp_path / "kill_switch"))
    ks.disengage()
    return ks


class TestFourGateChain:
    """The scheduler's gate 4 + OrderService's gates 1-3, chained end-to-end."""

    def test_all_four_gates_pass_and_order_executes(
        self, mock_broker, permissive_governor, champion_signal, tmp_path, monkeypatch,
    ):
        """All four gates open → champion signal executes and broker is called."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        svc = SchedulerService(db_path=None)
        svc.set_auto_execute(True)
        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=_disengaged_kill_switch(tmp_path))

        ok, msg, order_id = svc.execute_champion_signal(service, champion_signal)
        assert ok, f"Expected success, got: {msg}"
        assert msg == "order submitted"
        assert order_id == "test-id"
        mock_broker.submit_order.assert_called_once()
        submitted = mock_broker.submit_order.call_args[0][0]
        assert submitted.symbol == "AAPL"
        assert submitted.side == OrderSide.BUY
        assert submitted.qty == 5

    def test_gate4_alone_blocks_auto_execute(
        self, mock_broker, permissive_governor, champion_signal, tmp_path, monkeypatch,
    ):
        """Gate 4 is checked FIRST — auto_execute off blocks before gates 1-3."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        # auto_execute stays at its default (False) — gates 1-3 would pass.
        svc = SchedulerService(db_path=None)
        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=_disengaged_kill_switch(tmp_path))

        ok, msg, order_id = svc.execute_champion_signal(service, champion_signal)
        assert not ok
        assert "gate 4" in msg.lower()
        assert order_id is None
        mock_broker.submit_order.assert_not_called()
        mock_broker.get_account.assert_not_called()  # gates 1-3 never ran

    def test_gate1_config_still_blocks_even_with_gate4(
        self, mock_broker, permissive_governor, champion_signal, tmp_path, monkeypatch,
    ):
        """Gate 4 open does NOT bypass gate 1 — invalid TRADING_MODE still blocks."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="bogus", ENABLE_LIVE_TRADING=False))

        svc = SchedulerService(db_path=None)
        svc.set_auto_execute(True)
        service = OrderService(broker=mock_broker, governor=permissive_governor,
                               kill_switch=_disengaged_kill_switch(tmp_path))

        ok, msg, order_id = svc.execute_champion_signal(service, champion_signal)
        assert not ok
        assert "invalid TRADING_MODE" in msg
        assert "gate 4" not in msg  # the block came from gate 1, not gate 4
        assert order_id is None
        mock_broker.submit_order.assert_not_called()

    def test_gate2_risk_governor_still_blocks_even_with_gate4(
        self, mock_broker, champion_signal, tmp_path, monkeypatch,
    ):
        """Gate 4 open does NOT bypass gate 2 — RiskGovernor still blocks."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        # Strict governor: any notional over $100 is rejected.
        strict = RiskGovernor({
            "max_position_notional": 100,
            "kill_switch_file": str(tmp_path / "governor_kill_switch"),
        })

        svc = SchedulerService(db_path=None)
        svc.set_auto_execute(True)
        service = OrderService(broker=mock_broker, governor=strict,
                               kill_switch=_disengaged_kill_switch(tmp_path))

        ok, msg, order_id = svc.execute_champion_signal(service, champion_signal)
        assert not ok
        assert "risk governor" in msg.lower()
        assert order_id is None
        mock_broker.submit_order.assert_not_called()

    def test_gate3_kill_switch_still_blocks_even_with_gate4(
        self, mock_broker, permissive_governor, champion_signal, tmp_path, monkeypatch,
    ):
        """Gate 4 open does NOT bypass gate 3 — kill switch still blocks."""
        monkeypatch.setattr("cudaquant.execution.order_service.settings",
                            _make_settings(TRADING_MODE="paper", ENABLE_LIVE_TRADING=False))

        svc = SchedulerService(db_path=None)
        svc.set_auto_execute(True)
        ks = KillSwitch(str(tmp_path / "kill_switch"))
        ks.engage("test gate 3")

        try:
            service = OrderService(broker=mock_broker, governor=permissive_governor,
                                   kill_switch=ks)
            ok, msg, order_id = svc.execute_champion_signal(service, champion_signal)
            assert not ok
            assert "kill switch" in msg.lower()
            assert order_id is None
            mock_broker.submit_order.assert_not_called()
        finally:
            ks.disengage()


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
