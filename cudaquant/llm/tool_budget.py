"""Budget / rate-limit layer for web research tools.

Mirrors ``LLMBudget`` (cudaquant.llm.agent) but tracks per-tool call counts
("brave", "tavily", "firecrawl") in addition to the global daily call and USD
spend limits. Day boundaries reset the counters automatically on the next call.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

KNOWN_TOOLS = ("brave", "tavily", "firecrawl")


class SearchBudget:
    """Tracks and enforces daily limits on web research tool calls."""

    def __init__(self, daily_calls: int = 100, daily_spend_usd: float = 1.0):
        self.daily_calls = daily_calls
        self.daily_spend_usd = daily_spend_usd
        self._per_tool_calls: dict[str, int] = {t: 0 for t in KNOWN_TOOLS}
        self._total_calls = 0
        self._daily_cost = 0.0
        self._last_reset_day = datetime.utcnow().date()

    def _reset_if_new_day(self) -> None:
        today = datetime.utcnow().date()
        if today != self._last_reset_day:
            self._per_tool_calls = {t: 0 for t in KNOWN_TOOLS}
            self._total_calls = 0
            self._daily_cost = 0.0
            self._last_reset_day = today

    def can_call(self, tool_name: str) -> tuple[bool, str]:
        """Return ``(allowed, reason)`` for a call to ``tool_name``."""
        if tool_name not in KNOWN_TOOLS:
            return False, f"unknown tool: {tool_name}"
        self._reset_if_new_day()
        if self._total_calls >= self.daily_calls:
            return False, "daily call limit reached"
        if self._daily_cost >= self.daily_spend_usd:
            return False, "daily USD budget exhausted"
        return True, "ok"

    def record_call(self, tool_name: str, cost_usd: float = 0.0) -> None:
        """Record a completed call (and its USD cost, if known)."""
        if tool_name not in KNOWN_TOOLS:
            logger.warning("ignoring record_call for unknown tool: %s", tool_name)
            return
        self._reset_if_new_day()
        self._per_tool_calls[tool_name] += 1
        self._total_calls += 1
        self._daily_cost += max(0.0, cost_usd)

    def get_status(self) -> dict:
        """Return a snapshot of usage against limits."""
        self._reset_if_new_day()
        return {
            "total_calls": self._total_calls,
            "daily_calls_limit": self.daily_calls,
            "daily_cost_usd": round(self._daily_cost, 4),
            "daily_spend_limit_usd": self.daily_spend_usd,
            "per_tool_calls": dict(self._per_tool_calls),
            "reset_day": str(self._last_reset_day),
        }
