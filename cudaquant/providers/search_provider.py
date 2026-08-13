"""Market symbol search + quote lookup — FMP with deterministic synthetic fallback.

Reads the API key from settings/env (``FMP_API_KEY``); no exception ever
escapes a call. Search tries FMP's current ``/stable/`` endpoints
(``search-name`` then ``search-symbol``; the bare ``/stable/search`` path is
not documented in the current API and legacy ``/api/v3/`` paths 403 for
non-legacy accounts) and falls back to a small in-memory symbol list filtered
by substring. Quotes fall back to a synthetic last-close via
``SyntheticDataGenerator``.

Environment: FMP_API_KEY
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import dotenv_values

from cudaquant.config.settings import settings
from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator

logger = logging.getLogger(__name__)

_BASE_URL = "https://financialmodelingprep.com/stable"

# Fallback directory used when no API key is present or the API is unreachable.
_FALLBACK_SYMBOLS: list[tuple[str, str]] = [
    ("AAPL", "Apple Inc."),
    ("MSFT", "Microsoft Corporation"),
    ("GOOGL", "Alphabet Inc."),
    ("AMZN", "Amazon.com Inc."),
    ("NVDA", "NVIDIA Corporation"),
    ("META", "Meta Platforms Inc."),
    ("TSLA", "Tesla Inc."),
    ("JPM", "JPMorgan Chase & Co."),
    ("V", "Visa Inc."),
    ("JNJ", "Johnson & Johnson"),
    ("WMT", "Walmart Inc."),
    ("PG", "Procter & Gamble Company"),
    ("HD", "Home Depot Inc."),
    ("DIS", "Walt Disney Company"),
    ("NFLX", "Netflix Inc."),
]


def _api_key() -> str:
    """Resolve FMP_API_KEY from settings, process env, or the project .env."""
    return (
        getattr(settings, "FMP_API_KEY", None)
        or os.getenv("FMP_API_KEY")
        or dotenv_values().get("FMP_API_KEY")
        or ""
    )


def _map_search_row(row: dict) -> dict:
    """Map one FMP search result to the canonical ``{"symbol", ...}`` shape."""
    return {
        "symbol": str(row.get("symbol") or ""),
        "name": str(row.get("name") or ""),
        "exchange": str(row.get("exchangeShortName") or row.get("exchange") or ""),
        "type": str(row.get("type") or ""),
    }


class SearchProvider:
    """Market symbol search + quote lookup (FMP first, synthetic fallback)."""

    def __init__(self):
        self.api_key = _api_key()
        self._client = httpx.Client(timeout=10.0)
        self._synthetic = SyntheticDataGenerator(seed=42)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET an FMP endpoint, returning parsed JSON or None on any failure."""
        if not self.api_key:
            return None
        query = dict(params or {})
        query["apikey"] = self.api_key
        try:
            resp = self._client.get(f"{_BASE_URL}/{path}", params=query)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # network, HTTP, decode errors → degrade gracefully
            logger.warning("FMP %s failed: %s", path, e)
            return None

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search for symbols by ticker or company name (never raises)."""
        query = str(query or "").strip()
        if not query:
            return []
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            limit = 10
        # search-name covers both names and symbols; search-symbol is a second
        # pass for symbol-only matches when the name search comes up empty.
        for path in ("search-name", "search-symbol"):
            data = self._get(path, {"query": query, "limit": limit})
            if isinstance(data, list) and data:
                return [_map_search_row(row) for row in data if isinstance(row, dict)]
        return self._fallback_search(query, limit)

    def get_quote(self, symbol: str) -> dict:
        """Return a quote for ``symbol`` or {} when unavailable (never raises)."""
        symbol = str(symbol or "").strip().upper()
        if not symbol:
            return {}
        data = self._get("quote", {"symbol": symbol})
        if isinstance(data, list) and data and isinstance(data[0], dict):
            row = data[0]
            return {
                "symbol": str(row.get("symbol") or symbol),
                "price": row.get("price") or 0.0,
                "change": row.get("change") or 0.0,
                "changePercent": row.get("changesPercentage") or 0.0,
                "prevClose": row.get("previousClose") or 0.0,
                "open": row.get("open") or 0.0,
                "high": row.get("high") or 0.0,
                "low": row.get("low") or 0.0,
                "volume": row.get("volume") or 0,
            }
        return self._synthetic_quote(symbol)

    def _fallback_search(self, query: str, limit: int) -> list[dict]:
        """Filter the in-memory directory by case-insensitive substring."""
        needle = query.upper()
        results: list[dict] = []
        for symbol, name in _FALLBACK_SYMBOLS:
            if needle in symbol or needle in name.upper():
                results.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "exchange": "US",
                        "type": "stock",
                    }
                )
                if len(results) >= limit:
                    break
        return results

    def _synthetic_quote(self, symbol: str) -> dict:
        """Build a quote from the last two generated daily bars."""
        try:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=7)
            df = self._synthetic.generate_bars(
                symbols=[symbol],
                start=start,
                end=end,
                frequency=BarFrequency.DAY_1,
                seed=42,
            )
            if len(df) < 2:
                return {}
            last, prev = df.iloc[-1], df.iloc[-2]
            prev_close = float(prev["close"])
            price = float(last["close"])
            change = price - prev_close
            change_percent = (change / prev_close * 100.0) if prev_close else 0.0
            return {
                "symbol": symbol,
                "price": price,
                "change": change,
                "changePercent": change_percent,
                "prevClose": prev_close,
                "open": float(last["open"]),
                "high": float(last["high"]),
                "low": float(last["low"]),
                "volume": int(last["volume"]),
            }
        except Exception as e:  # synthetic generation must never reach callers
            logger.warning("Synthetic quote failed for %s: %s", symbol, e)
            return {}

    def close(self) -> None:
        """Release the underlying HTTP client."""
        self._client.close()
