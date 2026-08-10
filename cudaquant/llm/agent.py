"""LLM research agent — advisory only. Never controls trading.

The LLM acts as a RESEARCHER, not a trader. It may:
- Analyze strategy performance
- Propose hypotheses for new experiments
- Diagnose failure modes
- Generate structured experiment proposals

It may NEVER:
- Place orders or enable live trading
- Alter credentials or risk controls
- Self-promote strategies
- Execute arbitrary code
"""

import json
import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from cudaquant.llm.tool_budget import SearchBudget

logger = logging.getLogger(__name__)


class ExperimentProposal(BaseModel):
    """Structured output from the LLM research agent."""

    hypothesis: str = Field(..., description="The research hypothesis to test")
    reasoning_summary: str = Field(..., description="Why this hypothesis is worth testing")
    proposed_change: str = Field(..., description="What parameters or features to change")
    metrics_to_evaluate: list[str] = Field(
        default_factory=lambda: ["sharpe", "max_drawdown", "win_rate"],
        description="Metrics to evaluate success",
    )
    expected_failure_modes: list[str] = Field(
        default_factory=list,
        description="Ways this experiment could fail",
    )
    priority: int = Field(default=3, ge=1, le=5, description="1=highest, 5=lowest")


class LLMBudget:
    """Tracks and enforces LLM API spending limits."""

    def __init__(
        self,
        daily_usd: float = 1.0,
        monthly_usd: float = 20.0,
        max_calls_per_day: int = 50,
        max_tokens_per_call: int = 8000,
    ):
        self.daily_usd = daily_usd
        self.monthly_usd = monthly_usd
        self.max_calls_per_day = max_calls_per_day
        self.max_tokens_per_call = max_tokens_per_call
        self._daily_calls = 0
        self._daily_cost = 0.0
        self._monthly_cost = 0.0
        self._last_reset_day = datetime.utcnow().date()

    def can_call(self, estimated_tokens: int = 1000) -> tuple[bool, str]:
        """Check if a call is within budget."""
        today = datetime.utcnow().date()
        if today != self._last_reset_day:
            self._daily_calls = 0
            self._daily_cost = 0.0
            self._last_reset_day = today

        if self._daily_calls >= self.max_calls_per_day:
            return False, "daily call limit reached"
        if self._daily_cost >= self.daily_usd:
            return False, "daily USD budget exhausted"
        if self._monthly_cost >= self.monthly_usd:
            return False, "monthly USD budget exhausted"
        if estimated_tokens > self.max_tokens_per_call:
            return False, f"estimated tokens ({estimated_tokens}) exceeds max per call ({self.max_tokens_per_call})"

        return True, "ok"

    def record_call(self, tokens: int, cost_usd: float) -> None:
        self._daily_calls += 1
        self._daily_cost += cost_usd
        self._monthly_cost += cost_usd

    def get_status(self) -> dict:
        return {
            "daily_calls": self._daily_calls,
            "daily_cost_usd": round(self._daily_cost, 4),
            "monthly_cost_usd": round(self._monthly_cost, 4),
            "daily_limit": self.max_calls_per_day,
            "daily_budget_usd": self.daily_usd,
            "monthly_budget_usd": self.monthly_usd,
        }


class LLMResearchAgent:
    """Advisory research agent backed by an LLM API.

    Works fully without an API key — all methods return sensible defaults
    or structured guidance when LLM is unavailable.
    """

    def __init__(
        self,
        provider: Any = None,
        budget: LLMBudget | None = None,
        search_tools: dict | None = None,
        search_budget: SearchBudget | None = None,
        search_cache: Any = None,
    ):
        self._provider = provider
        self.budget = budget or LLMBudget()
        self._enabled = provider is not None
        self.search_budget = search_budget or SearchBudget()
        self.search_cache = search_cache
        self.search_tools = search_tools
        if self.search_tools is None:
            try:
                from cudaquant.llm.tools import BraveSearchTool, FirecrawlTool, TavilySearchTool

                self.search_tools = {
                    "brave": BraveSearchTool(),
                    "tavily": TavilySearchTool(),
                    "firecrawl": FirecrawlTool(),
                }
            except Exception as e:  # pragma: no cover - httpx is a project dependency
                logger.warning("Web research tools disabled: %s", e)
                self.search_tools = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def analyze_performance(
        self,
        metrics: dict,
        trades: list[dict],
        regime_stats: dict | None = None,
    ) -> str:
        """Generate a performance analysis report.

        Works without LLM — returns structured text analysis based on metrics.
        """
        if not self._enabled:
            return self._local_analysis(metrics, trades, regime_stats)

        # With LLM: call API
        web_context = self._gather_web_context(self._symbols_from(metrics, trades))
        prompt = self._build_analysis_prompt(metrics, trades, regime_stats, web_context)
        try:
            can_call, reason = self.budget.can_call()
            if not can_call:
                return f"LLM call blocked: {reason}\n\n" + self._local_analysis(metrics, trades, regime_stats)

            response = self._provider.generate(prompt, max_tokens=1000)
            self.budget.record_call(tokens=1000, cost_usd=0.005)
            return response
        except Exception as e:
            logger.warning("LLM analysis failed: %s", e)
            return self._local_analysis(metrics, trades, regime_stats)

    def propose_experiment(
        self,
        context: dict,
    ) -> ExperimentProposal:
        """Propose a new experiment based on current state.

        Works without LLM — returns a generic improvement proposal.
        """
        if not self._enabled:
            return self._default_proposal(context)

        web_context = self._gather_web_context(self._symbols_from_context(context))
        prompt = self._build_proposal_prompt(context, web_context)
        try:
            can_call, reason = self.budget.can_call()
            if not can_call:
                logger.info("LLM proposal blocked: %s", reason)
                return self._default_proposal(context)

            response = self._provider.generate(prompt, max_tokens=500)
            # Parse structured output
            try:
                # Try to extract JSON from response
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(response[json_start:json_end])
                    return ExperimentProposal(**data)
            except (json.JSONDecodeError, Exception):
                pass

            self.budget.record_call(tokens=500, cost_usd=0.0025)
            return ExperimentProposal(
                hypothesis=response[:200],
                reasoning_summary="LLM-generated proposal (parsing failed, using raw response)",
                proposed_change="see hypothesis",
            )
        except Exception as e:
            logger.warning("LLM proposal failed: %s", e)
            return self._default_proposal(context)

    def diagnose_failures(self, failed_trades: list[dict]) -> str:
        """Analyze losing trades for patterns."""
        if not failed_trades or not self._enabled:
            return self._local_failure_analysis(failed_trades)

        prompt = self._build_failure_prompt(failed_trades)
        try:
            response = self._provider.generate(prompt, max_tokens=800)
            return response
        except Exception:
            return self._local_failure_analysis(failed_trades)

    def _build_analysis_prompt(
        self,
        metrics: dict,
        trades: list[dict],
        regime_stats: dict | None = None,
        web_context: dict | None = None,
    ) -> str:
        return json.dumps({
            "task": "analyze_trading_performance",
            "metrics": {k: v for k, v in metrics.items() if isinstance(v, (int, float, str, bool))},
            "trade_count": len(trades),
            "regime_stats": regime_stats or {},
            "web_search_results": (web_context or {}).get("web_search_results", []),
            "tools_available": (
                "You have access to web search (Brave/Tavily) and URL scraping (Firecrawl). "
                "If you need current information to analyze this performance, request it."
            ),
            "instructions": (
                "Analyze the performance. Identify strengths, weaknesses, and suggest one "
                "concrete improvement. Use the web search results only if relevant to the "
                "analysis; ignore them if not."
            ),
        })

    def _build_proposal_prompt(self, context: dict, web_context: dict | None = None) -> str:
        return json.dumps({
            "task": "propose_experiment",
            "context": context,
            "web_search_results": (web_context or {}).get("web_search_results", []),
            "tools_available": (
                "You have access to web search (Brave/Tavily) and URL scraping (Firecrawl). "
                "If you need current information to analyze this performance, request it."
            ),
            "format": "Return JSON with keys: hypothesis, reasoning_summary, proposed_change, metrics_to_evaluate, expected_failure_modes, priority",
        })

    def _build_failure_prompt(self, failed_trades: list[dict]) -> str:
        return json.dumps({
            "task": "diagnose_failures",
            "failed_trade_count": len(failed_trades),
            "sample_trades": failed_trades[:10],
            "instructions": "Identify patterns in losing trades. Are there common entry conditions, times, or regime types?",
        })

    @staticmethod
    def _symbols_from(metrics: dict, trades: list[dict]) -> list[str]:
        """Collect symbol identifiers from metrics/trades for web research."""
        symbols: set[str] = set()
        m_symbol = metrics.get("symbol")
        if isinstance(m_symbol, str) and m_symbol.strip():
            symbols.add(m_symbol.strip().upper())
        elif isinstance(m_symbol, (list, tuple)):
            symbols.update(s.strip().upper() for s in m_symbol if isinstance(s, str) and s.strip())
        for trade in trades:
            symbol = trade.get("symbol")
            if isinstance(symbol, str) and symbol.strip():
                symbols.add(symbol.strip().upper())
        return sorted(symbols)

    @staticmethod
    def _symbols_from_context(context: dict) -> list[str]:
        """Collect symbol identifiers from a proposal context dict."""
        symbols: set[str] = set()
        for key in ("symbols", "symbol"):
            value = context.get(key)
            if isinstance(value, str) and value.strip():
                symbols.add(value.strip().upper())
            elif isinstance(value, (list, tuple)):
                symbols.update(s.strip().upper() for s in value if isinstance(s, str) and s.strip())
        return sorted(symbols)

    def _gather_web_context(self, symbols: list[str], max_results: int = 3) -> dict:
        """Run budgeted, cached web searches for symbols; advisory only.

        Returns a dict with ``web_search_results`` for embedding in an LLM
        prompt. Never raises; failures yield partial or empty context.
        """
        if not self.search_tools or not symbols:
            return {"web_search_results": []}
        gathered = []
        for symbol in symbols[:3]:
            query = f"{symbol} stock news today"
            results = self._cached_search(query, max_results)
            if results:
                gathered.append({"symbol": symbol, "query": query, "results": results})
        return {"web_search_results": gathered}

    def _cached_search(self, query: str, max_results: int = 3) -> list[dict]:
        """Search Brave then Tavily, cache-first, budget-gated.

        Returns the first non-empty result set; ``[]`` if none of the tools
        produced results or the budget blocked the calls.
        """
        if self.search_cache is not None:
            for tool_name in ("brave", "tavily"):
                try:
                    cached = self.search_cache.get(tool_name, query)
                except Exception as e:
                    logger.warning("cache read failed for %s/%r: %s", tool_name, query, e)
                    continue
                if cached is not None:
                    try:
                        return json.loads(cached)
                    except (json.JSONDecodeError, TypeError):
                        continue

        for tool_name, call in (
            ("brave", lambda t, q: t.search(q, count=max_results)),
            ("tavily", lambda t, q: t.search(q, max_results=max_results)),
        ):
            tool = self.search_tools.get(tool_name)
            if tool is None:
                continue
            can, reason = self.search_budget.can_call(tool_name)
            if not can:
                logger.info("%s search skipped: %s", tool_name.capitalize(), reason)
                continue
            try:
                results = call(tool, query)
            except Exception as e:
                logger.warning("%s search error for %r: %s", tool_name, query, e)
                results = []
            self.search_budget.record_call(tool_name)
            if results and self.search_cache is not None:
                try:
                    self.search_cache.set(tool_name, query, json.dumps(results))
                except Exception as e:
                    logger.warning("cache write failed for %s/%r: %s", tool_name, query, e)
            if results:
                return results
        return []

    def _local_analysis(self, metrics: dict, trades: list[dict], regime_stats: dict | None = None) -> str:
        """Local analysis without LLM."""
        lines = ["# Strategy Performance Analysis (automated)\n"]

        sharpe = metrics.get("sharpe", 0)
        max_dd = metrics.get("max_drawdown", 0)
        win_rate = metrics.get("win_rate", 0)
        profit_factor = metrics.get("profit_factor", 0)
        n_trades = metrics.get("trade_count", len(trades))

        lines.append(f"Sharpe: {sharpe:.3f}")
        lines.append(f"Max Drawdown: {max_dd:.1%}")
        lines.append(f"Win Rate: {win_rate:.1%}")
        lines.append(f"Profit Factor: {profit_factor:.2f}")
        lines.append(f"Total Trades: {n_trades}")
        lines.append("")

        if sharpe < 0:
            lines.append("⚠️  Negative Sharpe — strategy is losing money after risk adjustment.")
        elif sharpe < 0.5:
            lines.append("⚡ Low Sharpe — strategy has marginal risk-adjusted returns.")
        elif sharpe < 1.0:
            lines.append("✓  Moderate Sharpe — strategy shows some edge.")

        if max_dd > 0.3:
            lines.append("⚠️  Large drawdown (>30%) — consider tighter risk controls.")
        if n_trades < 20:
            lines.append("⚠️  Low trade count — statistical significance may be limited.")
        if profit_factor < 1.0:
            lines.append("⚠️  Profit factor < 1 — gross losses exceed gross profits.")

        if regime_stats:
            lines.append("\n## Regime Performance")
            for regime, stats in sorted(regime_stats.items()):
                if stats.get("trade_count", 0) > 0:
                    lines.append(f"- {regime}: {stats['trade_count']} trades, "
                                 f"win_rate={stats.get('win_rate', 0):.1%}, "
                                 f"avg_pnl={stats.get('avg_pnl', 0):.4f}")

        return "\n".join(lines)

    def _default_proposal(self, context: dict) -> ExperimentProposal:
        """Default experiment proposal when LLM is unavailable."""
        return ExperimentProposal(
            hypothesis="Parameter sensitivity analysis for current strategy",
            reasoning_summary="Systematic parameter perturbation to discover robust regions. "
                             "Generated automatically (LLM not configured).",
            proposed_change="Vary key parameters (lookback window, threshold) by ±20%",
            metrics_to_evaluate=["sharpe", "max_drawdown", "win_rate", "profit_factor"],
            expected_failure_modes=[
                "Parameter overfitting to recent regime",
                "Insufficient trade count in some parameter regions",
            ],
            priority=3,
        )

    def _local_failure_analysis(self, failed_trades: list[dict]) -> str:
        """Local failure analysis without LLM."""
        if not failed_trades:
            return "No failed trades to analyze."

        total_loss = sum(t.get("pnl", 0) for t in failed_trades)
        avg_loss = total_loss / len(failed_trades) if failed_trades else 0

        lines = [
            "# Trade Failure Analysis\n",
            f"Failed trades: {len(failed_trades)}",
            f"Total loss: ${total_loss:,.2f}",
            f"Average loss: ${avg_loss:,.2f}",
            "",
            "Consider reviewing:",
            "- Entry timing relative to market regime",
            "- Position sizing relative to volatility",
            "- Stop-loss placement and activation",
            "- Transaction cost impact on smaller trades",
        ]
        return "\n".join(lines)
