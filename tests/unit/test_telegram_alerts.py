"""TelegramAlerter unit tests — graceful degradation + outbound payload.

Targets ``cudaquant.alerts.telegram.TelegramAlerter``. The alerter reads the
module-level ``settings`` singleton, so tests patch attributes on it via
monkeypatch. Network access is faked by swapping ``sys.modules["httpx"]`` —
the module imports httpx lazily inside ``send()``.
"""

import sys

import pytest

from cudaquant.alerts.telegram import TelegramAlerter
from cudaquant.config.settings import settings


class FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code


class FakeHttpx:
    """Records post() calls; optionally raises or returns a fixed status."""

    def __init__(self, status_code: int = 200, exc: Exception | None = None):
        self._status_code = status_code
        self._exc = exc
        self.calls: list[dict] = []

    def post(self, url: str, json: dict | None = None, timeout: float | None = None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self._exc is not None:
            raise self._exc
        return FakeResponse(self._status_code)


@pytest.fixture
def fake_httpx(monkeypatch):
    """Install a fake httpx module for the alerter's lazy import."""

    def _install(fake: FakeHttpx) -> FakeHttpx:
        monkeypatch.setitem(sys.modules, "httpx", fake)
        return fake

    return _install


def _configured_alerter(monkeypatch, token=None, chat_id=None) -> TelegramAlerter:
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", token)
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", chat_id)
    return TelegramAlerter()


def test_alerter_reads_credentials_from_settings(monkeypatch):
    alerter = _configured_alerter(monkeypatch, token="tok123", chat_id="456")
    assert alerter.token == "tok123"
    assert alerter.chat_id == "456"


def test_send_skipped_when_chat_id_unset(monkeypatch, fake_httpx):
    """No chat_id → send() returns False and never touches the network."""
    fake = fake_httpx(FakeHttpx(exc=AssertionError("network must not be called")))
    alerter = _configured_alerter(monkeypatch, token="tok123", chat_id=None)
    assert alerter.send("test") is False
    assert fake.calls == []


def test_send_skipped_when_token_unset(monkeypatch, fake_httpx):
    fake = fake_httpx(FakeHttpx(exc=AssertionError("network must not be called")))
    alerter = _configured_alerter(monkeypatch, token=None, chat_id="456")
    assert alerter.send("test") is False
    assert fake.calls == []


def test_send_posts_expected_payload(monkeypatch, fake_httpx):
    fake = fake_httpx(FakeHttpx(status_code=200))
    alerter = _configured_alerter(monkeypatch, token="tok123", chat_id="456")
    assert alerter.send("hello") is True
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == "https://api.telegram.org/bottok123/sendMessage"
    assert call["json"] == {
        "chat_id": "456",
        "text": "hello",
        "parse_mode": "HTML",
    }
    assert call["timeout"] == 10


def test_send_escapes_html_in_message(monkeypatch, fake_httpx):
    """parse_mode=HTML must not break on dynamic content like `<` or `&`."""
    fake = fake_httpx(FakeHttpx(status_code=200))
    alerter = _configured_alerter(monkeypatch, token="tok123", chat_id="456")
    alerter.send('<b>failure</b> & reason: "x<y"')
    assert fake.calls[0]["json"]["text"] == "&lt;b&gt;failure&lt;/b&gt; &amp; reason: &quot;x&lt;y&quot;"


def test_send_returns_false_on_http_error(monkeypatch, fake_httpx):
    fake_httpx(FakeHttpx(status_code=401))
    alerter = _configured_alerter(monkeypatch, token="tok123", chat_id="456")
    assert alerter.send("hello") is False


def test_send_returns_false_on_network_exception(monkeypatch, fake_httpx):
    fake = fake_httpx(FakeHttpx(exc=RuntimeError("connection refused")))
    alerter = _configured_alerter(monkeypatch, token="tok123", chat_id="456")
    assert alerter.send("hello") is False
    assert len(fake.calls) == 1  # the request was attempted
