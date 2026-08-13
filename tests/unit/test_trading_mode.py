"""TradingModeService safety tests — persistence, env gates, and the switch()
gate chain (paper→live requires env gates + confirm + kill switch + live
broker connection; live→paper is always allowed).

All tests are hermetic: temp DuckDB files (``tmp_path``), env vars via
``monkeypatch``, a file-based ``KillSwitch`` on a temp path, and a stub
OrderService — no network, no real broker, no Telegram.
"""

import json

import pytest

from cudaquant.config.settings import settings
from cudaquant.execution.trading_mode import LIVE_CONFIRM, TradingModeService
from cudaquant.risk.kill_switch import (
    LIVE_ACK_ENV,
    LIVE_ACK_VALUE,
    LIVE_MODE_ENV,
    LIVE_MODE_VALUE,
    KillSwitch,
)


def _noop_alert(message: str) -> None:
    """Stand-in for TradingModeService._alert: never touch the network."""


class StubOrderService:
    """OrderService stand-in that records set_mode / verify_live_connection calls."""

    def __init__(self, verify_result: tuple[bool, str] = (True, "ok")):
        self.verify_result = verify_result
        self.set_mode_calls: list[tuple[str, bool]] = []
        self.verify_calls = 0

    def set_mode(self, mode: str, paper: bool) -> None:
        self.set_mode_calls.append((mode, paper))

    def verify_live_connection(self) -> tuple[bool, str]:
        self.verify_calls += 1
        return self.verify_result


@pytest.fixture(autouse=True)
def _no_alerts(monkeypatch):
    """Alerting must never hit the network during unit tests."""
    monkeypatch.setattr(TradingModeService, "_alert", staticmethod(_noop_alert))


@pytest.fixture
def make_service(tmp_path, monkeypatch):
    """Build a TradingModeService with a stub OrderService, in paper. Returns
    a factory: ``make_service(verify_result, engaged) -> (service, stub)``.

    Does NOT touch the raw environment gates — tests opt in via
    ``live_env_gates`` / ``no_env_gates``."""
    monkeypatch.setattr(settings, "TRADING_MODE", "paper")

    def _make(
        verify_result: tuple[bool, str] = (True, "ok"),
        engaged: bool = False,
    ) -> tuple[TradingModeService, StubOrderService]:
        ks = KillSwitch(str(tmp_path / "kill_switch"))
        if engaged:
            ks.engage()
        svc = TradingModeService(db_path=None, kill_switch=ks)
        stub = StubOrderService(verify_result)
        svc.bind_order_service(stub)
        return svc, stub

    return _make


@pytest.fixture
def live_env_gates(monkeypatch):
    """Set BOTH raw environment gates required for live trading."""
    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    monkeypatch.setenv(LIVE_ACK_ENV, LIVE_ACK_VALUE)


@pytest.fixture
def no_env_gates(monkeypatch):
    """Clear BOTH raw environment gates (hermetic baseline)."""
    monkeypatch.delenv(LIVE_MODE_ENV, raising=False)
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)


# ── Boot / init_from_boot ───────────────────────────────────────────────────


def test_fresh_service_defaults_to_paper(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TRADING_MODE", "paper")
    svc = TradingModeService(db_path=None, kill_switch=KillSwitch(str(tmp_path / "kill_switch")))
    assert svc.state.desired == "paper"
    assert svc.state.effective == "paper"
    assert svc.effective_mode == "paper"
    assert svc.state.reason == ""


def test_boot_desired_from_settings_trading_mode(tmp_path, monkeypatch):
    """With no persisted state the desired mode comes from settings.TRADING_MODE,
    but effective fails safe to paper while the env gates are absent."""
    monkeypatch.setattr(settings, "TRADING_MODE", "live")
    monkeypatch.delenv(LIVE_MODE_ENV, raising=False)
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)
    svc = TradingModeService(db_path=None, kill_switch=KillSwitch(str(tmp_path / "kill_switch")))
    assert svc.state.desired == "live"
    assert svc.state.effective == "paper"
    assert svc.state.reason


def test_boot_live_when_settings_live_and_env_gates_hold(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TRADING_MODE", "live")
    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    monkeypatch.setenv(LIVE_ACK_ENV, LIVE_ACK_VALUE)
    svc = TradingModeService(db_path=None, kill_switch=KillSwitch(str(tmp_path / "kill_switch")))
    assert svc.state.desired == "live"
    assert svc.state.effective == "live"
    assert svc.state.reason == ""


def test_boot_live_blocked_by_engaged_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TRADING_MODE", "live")
    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    monkeypatch.setenv(LIVE_ACK_ENV, LIVE_ACK_VALUE)
    ks = KillSwitch(str(tmp_path / "kill_switch"))
    ks.engage()
    svc = TradingModeService(db_path=None, kill_switch=ks)
    assert svc.state.desired == "live"
    assert svc.state.effective == "paper"
    assert "kill switch" in svc.state.reason


# ── Persistence (DuckDB round trip) ─────────────────────────────────────────


def _seed_mode_row(db_path: str, value: str) -> None:
    import duckdb

    con = duckdb.connect(db_path)
    con.execute("INSERT OR REPLACE INTO trading_mode_state VALUES ('desired', ?)", [value])
    con.close()


def _assert_persisted_mode(db_path: str, expected: str) -> None:
    import duckdb

    con = duckdb.connect(db_path, read_only=True)
    row = con.execute("SELECT value FROM trading_mode_state WHERE key='desired'").fetchone()
    con.close()
    assert row is not None, "no persisted trading mode row"
    assert json.loads(row[0])["mode"] == expected


def test_persist_live_survives_new_instance_with_env_gates(tmp_path, monkeypatch):
    """switch('live') persists the desired mode; a fresh service on the same
    DuckDB boots live while the env gates hold, and fails safe to paper (with
    a reason) when the gates are gone."""
    monkeypatch.setattr(settings, "TRADING_MODE", "paper")
    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    monkeypatch.setenv(LIVE_ACK_ENV, LIVE_ACK_VALUE)
    db_path = str(tmp_path / "mode.duckdb")
    ks = KillSwitch(str(tmp_path / "kill_switch"))

    svc = TradingModeService(db_path=db_path, kill_switch=ks)
    stub = StubOrderService()
    svc.bind_order_service(stub)
    ok, _ = svc.switch("live", confirm=LIVE_CONFIRM)
    assert ok is True
    assert svc.state.desired == "live"

    # The row is really in DuckDB, not just in memory.
    _assert_persisted_mode(db_path, "live")

    # Fresh instance, env gates still set -> effective live.
    svc2 = TradingModeService(db_path=db_path, kill_switch=ks)
    assert svc2.state.desired == "live"
    assert svc2.state.effective == "live"
    assert svc2.state.reason == ""

    # Fresh instance, TRADING_MODE gate removed -> boot falls back to paper.
    monkeypatch.delenv(LIVE_MODE_ENV)
    svc3 = TradingModeService(db_path=db_path, kill_switch=ks)
    assert svc3.state.desired == "live"  # preference is kept
    assert svc3.state.effective == "paper"
    assert svc3.state.reason


def test_persisted_invalid_mode_value_falls_back(tmp_path, monkeypatch):
    """Valid JSON that is not a valid mode falls back to settings.TRADING_MODE
    instead of booting somewhere unexpected."""
    monkeypatch.setattr(settings, "TRADING_MODE", "paper")
    db_path = str(tmp_path / "mode.duckdb")
    ks = KillSwitch(str(tmp_path / "kill_switch"))
    TradingModeService(db_path=db_path, kill_switch=ks)  # create the table
    _seed_mode_row(db_path, json.dumps({"mode": "bogus"}))
    svc = TradingModeService(db_path=db_path, kill_switch=ks)
    assert svc.state.desired == "paper"
    assert svc.state.effective == "paper"


def test_persisted_missing_mode_key_falls_back(tmp_path, monkeypatch):
    """Valid JSON without a 'mode' key also falls back to settings.TRADING_MODE."""
    monkeypatch.setattr(settings, "TRADING_MODE", "paper")
    db_path = str(tmp_path / "mode.duckdb")
    ks = KillSwitch(str(tmp_path / "kill_switch"))
    TradingModeService(db_path=db_path, kill_switch=ks)  # create the table
    _seed_mode_row(db_path, json.dumps({"foo": "bar"}))
    svc = TradingModeService(db_path=db_path, kill_switch=ks)
    assert svc.state.desired == "paper"


def test_persisted_non_object_json_falls_back(tmp_path, monkeypatch):
    """A JSON value that is not an object must fall back safely to env —
    a corrupted persisted preference must never crash boot."""
    monkeypatch.setattr(settings, "TRADING_MODE", "paper")
    db_path = str(tmp_path / "mode.duckdb")
    ks = KillSwitch(str(tmp_path / "kill_switch"))
    TradingModeService(db_path=db_path, kill_switch=ks)  # create the table
    _seed_mode_row(db_path, json.dumps("not an object"))
    svc = TradingModeService(db_path=db_path, kill_switch=ks)
    assert svc.state.desired == "paper"
    assert svc.state.effective == "paper"


# ── switch() gate chain ─────────────────────────────────────────────────────


def test_switch_invalid_mode_rejected(make_service):
    svc, stub = make_service()
    ok, reason = svc.switch("bogus")
    assert ok is False
    assert "invalid mode" in reason
    assert stub.set_mode_calls == []
    assert stub.verify_calls == 0


def test_switch_live_without_env_gates_rejected(no_env_gates, make_service):
    """Gate 1: the .env acknowledgement is checked BEFORE confirm or broker."""
    svc, stub = make_service()
    ok, reason = svc.switch("live", confirm=LIVE_CONFIRM)
    assert ok is False
    assert "env gates" in reason
    assert stub.set_mode_calls == []
    assert stub.verify_calls == 0


def test_switch_live_without_confirm_rejected(live_env_gates, make_service):
    svc, stub = make_service()
    ok, reason = svc.switch("live", confirm="")
    assert ok is False
    assert "LIVE" in reason
    assert stub.set_mode_calls == []
    assert stub.verify_calls == 0


def test_switch_live_with_kill_switch_engaged_rejected(live_env_gates, make_service):
    """Gate 3: the kill switch blocks the switch before the broker is probed."""
    svc, stub = make_service(engaged=True)
    ok, reason = svc.switch("live", confirm=LIVE_CONFIRM)
    assert ok is False
    assert "kill switch" in reason
    assert stub.set_mode_calls == []
    assert stub.verify_calls == 0  # connection gate never reached


def test_switch_live_without_broker_connection_rejected(live_env_gates, make_service):
    """Gate 4: verify_live_connection() failure is passed through as the reason."""
    svc, stub = make_service(verify_result=(False, "no creds"))
    ok, reason = svc.switch("live", confirm=LIVE_CONFIRM)
    assert ok is False
    assert reason == "no creds"
    assert stub.set_mode_calls == []
    assert stub.verify_calls == 1


def test_switch_live_full_success(live_env_gates, make_service):
    svc, stub = make_service()
    ok, reason = svc.switch("live", confirm=LIVE_CONFIRM)
    assert ok is True
    assert stub.set_mode_calls == [("live", False)]
    assert svc.state.desired == "live"
    assert svc.state.effective == "live"
    assert svc.effective_mode == "live"


def test_switch_paper_always_allowed_even_with_kill_switch(live_env_gates, make_service, tmp_path):
    """live→paper requires no gates, no confirm, and works with the kill switch
    engaged — paper is always the safe direction."""
    svc, stub = make_service()
    assert svc.switch("live", confirm=LIVE_CONFIRM)[0] is True
    KillSwitch(str(tmp_path / "kill_switch")).engage()
    ok, reason = svc.switch("paper")
    assert ok is True
    assert stub.set_mode_calls == [("live", False), ("paper", True)]
    assert svc.state.desired == "paper"
    assert svc.state.effective == "paper"


def test_switch_paper_when_already_paper(make_service):
    svc, stub = make_service()
    ok, reason = svc.switch("paper")
    assert ok is True
    assert reason == "already in paper mode"
    assert stub.set_mode_calls == []
    assert stub.verify_calls == 0


def test_switch_live_when_already_live_is_idempotent(live_env_gates, make_service):
    """Switching to the already-active mode is a no-op — no re-run of gates,
    no confirm needed, no set_mode re-application."""
    svc, stub = make_service()
    assert svc.switch("live", confirm=LIVE_CONFIRM)[0] is True
    ok, reason = svc.switch("live")
    assert ok is True
    assert reason == "already in live mode"
    assert stub.set_mode_calls == [("live", False)]  # set_mode NOT re-applied


def test_set_mode_paper_flag_mapping(live_env_gates, make_service):
    """switch() must pass paper=False for live and paper=True for paper to
    OrderService.set_mode — the flag selects the broker endpoint."""
    svc, stub = make_service()
    assert svc.switch("live", confirm=LIVE_CONFIRM)[0] is True
    assert stub.set_mode_calls[-1] == ("live", False)
    assert svc.switch("paper")[0] is True
    assert stub.set_mode_calls[-1] == ("paper", True)


# ── Environment gate helpers ────────────────────────────────────────────────


def test_env_live_eligible_requires_both_gates(monkeypatch):
    monkeypatch.delenv(LIVE_MODE_ENV, raising=False)
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)

    ok, reason = TradingModeService.env_live_eligible()
    assert ok is False
    assert "env gates" in reason

    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    ok, _ = TradingModeService.env_live_eligible()
    assert ok is False  # ack missing

    monkeypatch.setenv(LIVE_MODE_ENV, "paper")
    monkeypatch.setenv(LIVE_ACK_ENV, LIVE_ACK_VALUE)
    ok, _ = TradingModeService.env_live_eligible()
    assert ok is False  # mode must be live

    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    ok, reason = TradingModeService.env_live_eligible()
    assert ok is True
    assert reason == ""


def test_live_ack_enabled_ignores_trading_mode(monkeypatch):
    """KillSwitch.is_live_ack_enabled() depends on the ack alone, regardless of
    TRADING_MODE — OrderService gate 1 relies on this."""
    monkeypatch.delenv(LIVE_MODE_ENV, raising=False)
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)
    assert KillSwitch.is_live_ack_enabled() is False

    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    assert KillSwitch.is_live_ack_enabled() is False  # ack still missing

    monkeypatch.setenv(LIVE_ACK_ENV, LIVE_ACK_VALUE)
    monkeypatch.setenv(LIVE_MODE_ENV, "paper")
    assert KillSwitch.is_live_ack_enabled() is True  # ack alone is enough

    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    assert KillSwitch.is_live_ack_enabled() is True  # mode is irrelevant

    monkeypatch.delenv(LIVE_ACK_ENV)
    assert KillSwitch.is_live_ack_enabled() is False
