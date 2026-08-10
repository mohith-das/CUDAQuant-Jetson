"""Risk governor and kill switch safety tests.

Targets the landed M1 implementations:
- ``cudaquant.risk.governor.RiskGovernor(config: dict)`` with
  ``pre_trade_check(order, account, positions, current_prices) -> (bool, str)``
  and ``kill()``. The governor FAILS CLOSED: anything unknown rejects the order.
- ``cudaquant.risk.kill_switch.KillSwitch(filepath=...)`` with
  ``engage()`` / ``is_engaged()`` / ``disengage()`` and the static
  ``is_live_mode_enabled()`` gate (requires BOTH ``TRADING_MODE=live`` AND
  ``ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISK``).

Every kill-switch test uses a tmp_path file so no sentinel is left in the repo.
"""

import pytest

from cudaquant.risk.governor import RiskGovernor
from cudaquant.risk.kill_switch import KillSwitch


@pytest.fixture
def config(tmp_path) -> dict:
    return {
        "max_position_notional": 100_000,
        "max_total_exposure": 500_000,
        "max_daily_trades": 50,
        "max_daily_loss": 5_000,
        "max_drawdown_pct": 20,
        "kill_switch_file": str(tmp_path / "kill_switch"),
    }


@pytest.fixture
def governor(config) -> RiskGovernor:
    return RiskGovernor(config)


def _order(qty: int = 10, price: float = 100.0, side: str = "buy") -> dict:
    return {"symbol": "AAPL", "side": side, "qty": qty, "price": price}


def _context(cash: float = 100_000.0, price: float = 100.0):
    """Minimal (account, positions, current_prices) for a fresh account."""
    return {"cash": cash}, {}, {"AAPL": price}


# ── Pre-trade gate ──────────────────────────────────────────────────────────


def test_pre_trade_check_approves_valid_order(governor):
    approved, reason = governor.pre_trade_check(_order(), *_context())
    assert approved is True
    assert reason == "approved"


def test_pre_trade_check_rejects_oversized_order(governor):
    # notional 200_000 > max_position_notional (100_000)
    approved, reason = governor.pre_trade_check(_order(qty=2000, price=100.0), *_context())
    assert approved is False
    assert reason == "position_notional_exceeded"


def test_pre_trade_check_rejects_zero_quantity(governor):
    approved, reason = governor.pre_trade_check(_order(qty=0), *_context())
    assert approved is False
    assert reason == "invalid_qty"


def test_pre_trade_check_rejects_negative_quantity(governor):
    approved, reason = governor.pre_trade_check(_order(qty=-5), *_context())
    assert approved is False
    assert reason == "invalid_qty"


def test_pre_trade_check_rejects_invalid_side(governor):
    approved, reason = governor.pre_trade_check(_order(side="hold"), *_context())
    assert approved is False
    assert reason == "invalid_side"


def test_pre_trade_check_rejects_missing_price_data(governor):
    order = {"symbol": "AAPL", "side": "buy", "qty": 10}
    approved, reason = governor.pre_trade_check(order, {"cash": 100_000}, {}, {})
    assert approved is False
    assert reason == "no_price_data"


def test_pre_trade_check_fails_closed_on_exposure_unknown(governor):
    """An unpriced existing position makes total exposure unknowable → reject."""
    account = {"cash": 100_000}
    positions = {"MSFT": 50}  # MSFT has no price in current_prices
    approved, reason = governor.pre_trade_check(
        _order(), account, positions, {"AAPL": 100.0}
    )
    assert approved is False
    assert reason == "exposure_unknown"


# ── Kill switch behavior ────────────────────────────────────────────────────


def test_kill_blocks_subsequent_orders(governor):
    assert governor.pre_trade_check(_order(), *_context())[0] is True
    governor.kill()
    approved, reason = governor.pre_trade_check(_order(), *_context())
    assert approved is False
    assert reason == "kill_switch_engaged"
    # Stays blocked on repeat attempts.
    assert governor.pre_trade_check(_order(), *_context())[0] is False


def test_is_alive_reflects_kill_state(governor):
    assert governor.is_alive() is True
    governor.kill()
    assert governor.is_alive() is False


def test_kill_switch_engage_disengage_cycle(tmp_path):
    switch = KillSwitch(str(tmp_path / "kill_switch"))
    assert not switch.is_engaged()
    switch.engage()
    assert switch.is_engaged()
    switch.disengage()
    assert not switch.is_engaged()
    switch.engage()
    assert switch.is_engaged()
    switch.disengage()
    assert not switch.is_engaged()


def test_kill_switch_engage_blocks_governor(tmp_path):
    """Engaging the kill switch must block even orders the governor approves."""
    switch = KillSwitch(str(tmp_path / "kill_switch"))
    governor = RiskGovernor({"kill_switch_file": str(tmp_path / "kill_switch")})
    assert governor.pre_trade_check(_order(), *_context())[0] is True
    switch.engage()
    try:
        assert switch.is_engaged()
        assert governor.pre_trade_check(_order(), *_context())[0] is False
    finally:
        switch.disengage()
    assert governor.pre_trade_check(_order(), *_context())[0] is True


def test_kill_switch_status_reports_reason(tmp_path):
    switch = KillSwitch(str(tmp_path / "kill_switch"))
    switch.engage(reason="manual-test")
    try:
        status = switch.status()
        assert status["engaged"] is True
        assert status["reason"] == "manual-test"
    finally:
        switch.disengage()
    assert switch.status()["engaged"] is False


# ── Live-mode gates ─────────────────────────────────────────────────────────


def test_kill_switch_live_mode_disabled_by_default(monkeypatch):
    """Safety-critical: no live trading unless BOTH env gates are satisfied."""
    monkeypatch.delenv("TRADING_MODE", raising=False)
    monkeypatch.delenv("ENABLE_LIVE_TRADING", raising=False)
    assert KillSwitch.is_live_mode_enabled() is False


def test_live_mode_requires_both_gates(monkeypatch):
    monkeypatch.delenv("TRADING_MODE", raising=False)
    monkeypatch.delenv("ENABLE_LIVE_TRADING", raising=False)

    monkeypatch.setenv("TRADING_MODE", "live")
    assert KillSwitch.is_live_mode_enabled() is False  # ack missing

    monkeypatch.setenv("ENABLE_LIVE_TRADING", "I_UNDERSTAND_LIVE_TRADING_RISK")
    assert KillSwitch.is_live_mode_enabled() is True

    monkeypatch.setenv("TRADING_MODE", "paper")
    assert KillSwitch.is_live_mode_enabled() is False  # mode must be live


def test_governor_cannot_enable_live_mode_without_env_gates(governor, monkeypatch):
    """A bypass attempt (set_live_mode(True)) must fail by default."""
    monkeypatch.delenv("TRADING_MODE", raising=False)
    monkeypatch.delenv("ENABLE_LIVE_TRADING", raising=False)
    assert governor.set_live_mode(True) is False
    assert governor.get_state()["live_mode"] is False


def test_config_defaults_match_risk_limits(tmp_path):
    """An empty config must still enforce the documented paper defaults."""
    governor = RiskGovernor({"kill_switch_file": str(tmp_path / "kill_switch")})
    assert governor.max_position_notional == 100_000
    assert governor.max_total_exposure == 500_000
    assert governor.max_daily_trades == 50
    assert governor.max_daily_loss == 5_000
    assert governor.max_drawdown_pct == 20
