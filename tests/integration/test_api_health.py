"""Integration tests for the FastAPI health/readiness endpoints.

These hit the real ASGI app through Starlette's TestClient — exercising
``cudaquant.api.app`` and ``cudaquant.api.routes.health`` end to end.
They also assert the SAFETY invariant that live trading is OFF by default,
which the readiness probe must faithfully report.

Test isolation (temp DB, no production DB touch) is handled by the
root conftest.py's pytest_configure hook — no per-file env setup needed.
"""

import pytest
from fastapi.testclient import TestClient

from cudaquant.api.app import app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_health_ok(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "timestamp" in body


def test_readiness_reports_ready(client: TestClient):
    resp = client.get("/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["checks"]["config_loaded"] is True


def test_readiness_reports_live_trading_off_by_default(client: TestClient):
    """SAFETY: the app must default to paper mode with live trading disabled,
    and the readiness probe must reflect that truthfully."""
    checks = client.get("/readiness").json()["checks"]
    assert checks["live_trading_enabled"] is False, "live trading must be OFF by default"
    assert checks["trading_mode"] == "paper", "default trading mode must be paper"
