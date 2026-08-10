"""Tests for LLM research web tools: clients, budget, cache, and agent wiring.

Network calls are mocked; the live-key smoke check lives in the manual
verification script (see task notes), not here.
"""

import json
from datetime import datetime, timedelta

import httpx

from cudaquant.config.settings import settings
from cudaquant.llm.agent import LLMResearchAgent
from cudaquant.llm.tool_budget import SearchBudget
from cudaquant.llm.tool_cache import SearchCache
from cudaquant.llm.tools import BraveSearchTool, FirecrawlTool, TavilySearchTool


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "https://example.com")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=req,
                response=httpx.Response(self.status_code, request=req),
            )

    def json(self):
        return self._payload


class FakeProvider:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return json.dumps({
            "hypothesis": "h",
            "reasoning_summary": "r",
            "proposed_change": "p",
        })


class StubSearchTool:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, count=5):
        self.calls.append((query, count))
        return self.results


# ── Tools: key handling ──────────────────────────────────────────────────────


def test_missing_keys_return_graceful_empties(monkeypatch):
    monkeypatch.setattr(settings, "BRAVE_SEARCH_API_KEY", None)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", None)
    monkeypatch.setattr(settings, "FIRECRAWL_API_KEY", None)

    assert BraveSearchTool().search("AAPL") == []
    assert TavilySearchTool().search("AAPL") == []
    assert FirecrawlTool().scrape("https://example.com") == ""


def test_empty_query_never_hits_network(monkeypatch):
    called = []

    def fake_get(url, **kwargs):
        called.append(True)
        return FakeResponse({"web": {"results": []}})

    monkeypatch.setattr("cudaquant.llm.tools.httpx.get", fake_get)
    tool = BraveSearchTool()
    tool.api_key = "k"
    assert tool.search("   ") == []
    assert not called


# ── Tools: Brave ─────────────────────────────────────────────────────────────


def test_brave_search_success(monkeypatch):
    payload = {
        "web": {"results": [
            {"title": "T1", "url": "u1", "description": "d1"},
            {"title": "T2", "url": "u2", "description": "d2"},
        ]}
    }
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(payload)

    monkeypatch.setattr("cudaquant.llm.tools.httpx.get", fake_get)
    tool = BraveSearchTool()
    tool.api_key = "test-key"
    results = tool.search("AAPL", count=2)

    assert results == [
        {"title": "T1", "url": "u1", "description": "d1"},
        {"title": "T2", "url": "u2", "description": "d2"},
    ]
    assert captured["url"] == BraveSearchTool.BASE_URL
    assert captured["kwargs"]["params"] == {"q": "AAPL", "count": 2}
    assert captured["kwargs"]["headers"]["X-Subscription-Token"] == "test-key"
    assert captured["kwargs"]["timeout"] == 15.0


def test_brave_search_http_error_returns_empty(monkeypatch):
    monkeypatch.setattr(
        "cudaquant.llm.tools.httpx.get",
        lambda url, **kwargs: FakeResponse({}, status_code=401),
    )
    tool = BraveSearchTool()
    tool.api_key = "k"
    assert tool.search("AAPL") == []


def test_brave_search_timeout_returns_empty(monkeypatch):
    def fake_get(url, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("cudaquant.llm.tools.httpx.get", fake_get)
    tool = BraveSearchTool()
    tool.api_key = "k"
    assert tool.search("AAPL") == []


# ── Tools: Tavily ────────────────────────────────────────────────────────────


def test_tavily_search_success(monkeypatch):
    payload = {"results": [{"title": "T", "url": "u", "content": "c"}]}
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(payload)

    monkeypatch.setattr("cudaquant.llm.tools.httpx.post", fake_post)
    tool = TavilySearchTool()
    tool.api_key = "k"
    results = tool.search("NVDA", max_results=5)

    assert results == [{"title": "T", "url": "u", "content": "c"}]
    assert captured["url"] == TavilySearchTool.BASE_URL
    assert captured["kwargs"]["json"] == {"api_key": "k", "query": "NVDA", "max_results": 5}


def test_tavily_timeout_returns_empty(monkeypatch):
    def fake_post(url, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("cudaquant.llm.tools.httpx.post", fake_post)
    tool = TavilySearchTool()
    tool.api_key = "k"
    assert tool.search("AAPL") == []


# ── Tools: Firecrawl ─────────────────────────────────────────────────────────


def test_firecrawl_scrape_success(monkeypatch):
    payload = {"success": True, "data": {"markdown": "# Hello"}}
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(payload)

    monkeypatch.setattr("cudaquant.llm.tools.httpx.post", fake_post)
    tool = FirecrawlTool()
    tool.api_key = "k"
    md = tool.scrape("https://example.com")

    assert md == "# Hello"
    assert captured["url"] == FirecrawlTool.BASE_URL
    assert captured["kwargs"]["json"] == {"url": "https://example.com"}
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer k"


def test_firecrawl_success_false_returns_empty(monkeypatch):
    monkeypatch.setattr(
        "cudaquant.llm.tools.httpx.post",
        lambda url, **kwargs: FakeResponse({"success": False, "error": "nope"}),
    )
    tool = FirecrawlTool()
    tool.api_key = "k"
    assert tool.scrape("https://example.com") == ""


def test_firecrawl_http_error_returns_empty(monkeypatch):
    monkeypatch.setattr(
        "cudaquant.llm.tools.httpx.post",
        lambda url, **kwargs: FakeResponse({}, status_code=500),
    )
    tool = FirecrawlTool()
    tool.api_key = "k"
    assert tool.scrape("https://example.com") == ""


# ── SearchBudget ─────────────────────────────────────────────────────────────


def test_budget_can_call_and_record():
    budget = SearchBudget(daily_calls=10, daily_spend_usd=1.0)
    assert budget.can_call("brave") == (True, "ok")
    budget.record_call("brave", cost_usd=0.1)
    assert budget.can_call("brave") == (True, "ok")

    status = budget.get_status()
    assert status["per_tool_calls"]["brave"] == 1
    assert status["total_calls"] == 1
    assert status["daily_cost_usd"] == 0.1


def test_budget_unknown_tool_graceful():
    budget = SearchBudget()
    assert budget.can_call("yahoo") == (False, "unknown tool: yahoo")
    budget.record_call("yahoo")  # ignored, no crash


def test_budget_call_limit_blocks():
    budget = SearchBudget(daily_calls=1)
    assert budget.can_call("brave")[0]
    budget.record_call("brave")
    assert budget.can_call("tavily") == (False, "daily call limit reached")


def test_budget_spend_limit_blocks():
    budget = SearchBudget(daily_spend_usd=0.05)
    assert budget.can_call("brave")[0]
    budget.record_call("brave", cost_usd=0.05)
    assert budget.can_call("brave") == (False, "daily USD budget exhausted")


def test_budget_resets_next_day():
    budget = SearchBudget(daily_calls=1)
    budget.record_call("brave")
    assert budget.can_call("tavily") == (False, "daily call limit reached")
    budget._last_reset_day = datetime.utcnow().date() - timedelta(days=1)
    assert budget.can_call("tavily") == (True, "ok")


# ── SearchCache ──────────────────────────────────────────────────────────────


def test_cache_set_get_and_overwrite(tmp_path):
    cache = SearchCache(str(tmp_path / "nested" / "cache.duckdb"), ttl_seconds=3600)
    assert cache.get("brave", "q") is None
    cache.set("brave", "q", '["a"]')
    assert cache.get("brave", "q") == '["a"]'
    cache.set("brave", "q", '["b"]')
    assert cache.get("brave", "q") == '["b"]'
    cache.close()


def test_cache_ttl_expiry_immediate():
    cache = SearchCache(":memory:", ttl_seconds=0)
    cache.set("brave", "q", '["a"]')
    assert cache.get("brave", "q") is None
    assert cache.clear_expired() == 1
    cache.close()


def test_cache_clear_expired_only_old_rows(tmp_path):
    cache = SearchCache(str(tmp_path / "c.duckdb"), ttl_seconds=3600)
    cache.set("brave", "q1", "x")
    cache.set("tavily", "q2", "y")
    cache._conn.execute(
        "UPDATE search_cache SET created_at = ? WHERE tool = 'tavily'",
        [datetime.utcnow() - timedelta(hours=2)],
    )
    assert cache.clear_expired() == 1
    assert cache.get("brave", "q1") == "x"
    assert cache.get("tavily", "q2") is None
    cache.close()


def test_cache_context_manager():
    with SearchCache(":memory:") as cache:
        cache.set("brave", "q", "z")
        assert cache.get("brave", "q") == "z"


# ── Agent wiring ─────────────────────────────────────────────────────────────


def test_analyze_performance_includes_web_context():
    provider = FakeProvider()
    stub = StubSearchTool([{"title": "AAPL News", "url": "https://x", "description": "d"}])
    agent = LLMResearchAgent(provider=provider, search_tools={"brave": stub})

    agent.analyze_performance({"sharpe": 1.2}, [{"symbol": "aapl"}])

    prompt = json.loads(provider.prompts[0])
    assert "tools_available" in prompt
    assert "web search (Brave/Tavily)" in prompt["tools_available"]
    assert prompt["web_search_results"][0]["symbol"] == "AAPL"
    assert prompt["web_search_results"][0]["results"][0]["title"] == "AAPL News"


def test_analyze_performance_uses_cache_second_call():
    provider = FakeProvider()
    cache = SearchCache(":memory:")
    stub = StubSearchTool([{"title": "T", "url": "u", "description": "d"}])
    agent = LLMResearchAgent(provider=provider, search_tools={"brave": stub}, search_cache=cache)

    agent.analyze_performance({}, [{"symbol": "AAPL"}])
    assert len(stub.calls) == 1
    agent.analyze_performance({}, [{"symbol": "AAPL"}])
    assert len(stub.calls) == 1  # served from cache
    assert cache.get("brave", "AAPL stock news today") is not None
    cache.close()


def test_analyze_performance_budget_blocked_no_search():
    provider = FakeProvider()
    stub = StubSearchTool([{"title": "T", "url": "u", "description": "d"}])
    budget = SearchBudget(daily_calls=0)
    agent = LLMResearchAgent(provider=provider, search_tools={"brave": stub}, search_budget=budget)

    agent.analyze_performance({"sharpe": 1.0}, [{"symbol": "AAPL"}])

    prompt = json.loads(provider.prompts[0])
    assert prompt["web_search_results"] == []
    assert stub.calls == []


def test_local_fallback_does_not_search():
    class BoomTool:
        def search(self, query, count=5):
            raise AssertionError("search must not run in local fallback mode")

    agent = LLMResearchAgent(provider=None, search_tools={"brave": BoomTool()})
    out = agent.analyze_performance({"sharpe": 1.0}, [{"symbol": "AAPL"}])

    assert out.startswith("# Strategy Performance Analysis")


def test_propose_experiment_includes_web_context():
    provider = FakeProvider()
    stub = StubSearchTool([{"title": "NVDA", "url": "u", "description": "d"}])
    agent = LLMResearchAgent(provider=provider, search_tools={"brave": stub})

    proposal = agent.propose_experiment({"symbols": ["nvda"]})

    prompt = json.loads(provider.prompts[0])
    assert "tools_available" in prompt
    assert prompt["web_search_results"][0]["query"] == "NVDA stock news today"
    assert proposal.hypothesis == "h"


def test_default_tool_construction_from_settings():
    """Default search_tools are built from settings without raising."""
    agent = LLMResearchAgent(provider=None)
    assert set(agent.search_tools) == {"brave", "tavily", "firecrawl"}
    assert agent.search_tools["brave"].api_key == settings.BRAVE_SEARCH_API_KEY
