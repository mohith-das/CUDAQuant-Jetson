"""API integration tests for the trading-mode toggle (/api/risk/*).

Exercises the real ASGI app through TestClient: auth enforcement, the GET
status payload, and the PUT /api/risk/trading-mode gate chain (paper→live
requires env gates + confirm "LIVE"; live→paper is always allowed).

Safety guards used here:
- The shared TradingModeService singleton (get_shared_trading_mode) is never
  left in live state: an autouse fixture stubs the broker-connection gate (no
  real broker/network) and restores paper after every test — the singleton may
  already exist from earlier tests in the session, so we never assume fresh
  state.
- The app lifespan's Telegram polling/alerting is silenced so tests make no
  real network calls.
"""

import pytest
from fastapi.testclient import TestClient

from cudaquant.api.app import app
from cudaquant.api.routes import risk_routes
from cudaquant.config.settings import settings
from cudaquant.execution.trading_mode import LIVE_CONFIRM, get_shared_trading_mode
from cudaquant.risk.kill_switch import (
    LIVE_ACK_ENV,
    LIVE_ACK_VALUE,
    LIVE_MODE_ENV,
    LIVE_MODE_VALUE,
)

pytestmark = pytest.mark.integration

TEST_TOKEN = "test-api-token"


class StubOrderService:
    """OrderService stand-in — no broker, no network, records mode calls."""

    def __init__(self):
        self.set_mode_calls: list[tuple[str, bool]] = []
        self.is_broker_connected = False

    def set_mode(self, mode: str, paper: bool) -> None:
        self.set_mode_calls.append((mode, paper))

    def verify_live_connection(self) -> tuple[bool, str]:
        return True, "ok"

    def get_kill_switch_state(self) -> dict:
        return {"engaged": False, "reason": None, "engaged_at": None}


def _noop_telegram_send(self, message: str) -> bool:
    return False


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient running the real app lifespan. Telegram polling and the
    startup alert are silenced for the module's lifetime so the lifespan makes
    no real network calls; both are restored when the client closes."""
    from cudaquant.alerts import telegram as telegram_mod

    orig_token = settings.TELEGRAM_BOT_TOKEN
    orig_chat_id = settings.TELEGRAM_CHAT_ID
    orig_send = telegram_mod.TelegramAlerter.send
    settings.TELEGRAM_BOT_TOKEN = ""
    settings.TELEGRAM_CHAT_ID = ""
    telegram_mod.TelegramAlerter.send = _noop_telegram_send
    try:
        with TestClient(app) as c:
            yield c
    finally:
        settings.TELEGRAM_BOT_TOKEN = orig_token
        settings.TELEGRAM_CHAT_ID = orig_chat_id
        telegram_mod.TelegramAlerter.send = orig_send


@pytest.fixture(autouse=True)
def _auth_token(monkeypatch):
    """Enforce auth deterministically instead of depending on the real .env token."""
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", TEST_TOKEN)


@pytest.fixture(autouse=True)
def _no_live_env_gates(monkeypatch):
    """Start every test with the live env gates absent (raw os.environ)."""
    monkeypatch.delenv(LIVE_MODE_ENV, raising=False)
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)


@pytest.fixture(autouse=True)
def _paper_singleton(monkeypatch):
    """Stub the broker-connection gate and guarantee the shared singleton is
    paper before AND after every test (the try/finally equivalent): a later
    test must never observe live state left by an earlier one. The stub is
    bound BEFORE any restore switch so no real broker is ever constructed."""
    tm = get_shared_trading_mode(settings.DUCKDB_PATH)
    stub = StubOrderService()
    monkeypatch.setattr(tm, "_order_service", stub)
    monkeypatch.setattr(risk_routes, "_order_service", stub)
    if tm.effective_mode != "paper":
        tm.switch("paper")
    yield stub
    if tm.effective_mode != "paper":
        tm.switch("paper")


# ── Auth enforcement ────────────────────────────────────────────────────────


def test_risk_status_requires_auth(client):
    resp = client.get("/api/risk/")
    assert resp.status_code == 401


# ── GET /api/risk/ ──────────────────────────────────────────────────────────


def test_risk_status_reports_paper_by_default(client):
    resp = client.get("/api/risk/", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["trading_mode"] == "paper"
    assert body["desired_mode"] == "paper"
    assert isinstance(body["env_live_eligible"], bool)
    assert body["env_live_eligible"] is False
    assert body["live_trading_enabled"] is False
    assert body["kill_switch_engaged"] is False
    assert body["mode_reason"] is None
    assert body["broker_connected"] is False


# ── PUT /api/risk/trading-mode ──────────────────────────────────────────────


def test_put_paper_returns_200(client):
    resp = client.put(
        "/api/risk/trading-mode",
        json={"mode": "paper"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["effective_mode"] == "paper"
    assert body["desired_mode"] == "paper"


def test_put_live_without_env_gates_rejected(client, monkeypatch):
    """SAFETY: the UI alone can never enable live trading — the .env
    acknowledgement gates are required first."""
    monkeypatch.delenv(LIVE_MODE_ENV, raising=False)
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)
    resp = client.put(
        "/api/risk/trading-mode",
        json={"mode": "live", "confirm": LIVE_CONFIRM},
        headers=_auth_headers(),
    )
    assert resp.status_code == 403
    assert "env gates" in resp.json()["detail"]


def test_put_live_without_confirm_rejected_even_with_env_gates(client, monkeypatch):
    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    monkeypatch.setenv(LIVE_ACK_ENV, LIVE_ACK_VALUE)
    resp = client.put(
        "/api/risk/trading-mode",
        json={"mode": "live"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 403
    assert "LIVE" in resp.json()["detail"]


def test_put_live_with_env_gates_and_confirm_succeeds(client, monkeypatch):
    """Full paper→live switch via the API succeeds only with env gates +
    confirm 'LIVE'; GET then reports live. The autouse fixture restores paper
    in teardown."""
    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    monkeypatch.setenv(LIVE_ACK_ENV, LIVE_ACK_VALUE)
    resp = client.put(
        "/api/risk/trading-mode",
        json={"mode": "live", "confirm": LIVE_CONFIRM},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["effective_mode"] == "live"
    assert body["desired_mode"] == "live"

    status = client.get("/api/risk/", headers=_auth_headers()).json()
    assert status["trading_mode"] == "live"
    assert status["live_trading_enabled"] is True


def test_put_live_then_paper_restores_mode(client, monkeypatch):
    """After flipping to live, a PUT back to paper restores the singleton so
    later tests in the session start from paper."""
    monkeypatch.setenv(LIVE_MODE_ENV, LIVE_MODE_VALUE)
    monkeypatch.setenv(LIVE_ACK_ENV, LIVE_ACK_VALUE)
    resp = client.put(
        "/api/risk/trading-mode",
        json={"mode": "live", "confirm": LIVE_CONFIRM},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["effective_mode"] == "live"

    resp = client.put(
        "/api/risk/trading-mode",
        json={"mode": "paper"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["effective_mode"] == "paper"

    status = client.get("/api/risk/", headers=_auth_headers()).json()
    assert status["trading_mode"] == "paper"
    assert status["live_trading_enabled"] is False
