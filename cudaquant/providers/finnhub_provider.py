"""Finnhub API client — news, insider sentiment.

Reads the API key from settings/env (``FINNHUB_API_KEY``); returns empty
results on any error so callers can degrade gracefully (no key, network
failure, bad symbol, HTTP error, or non-JSON response).

Environment: FINNHUB_API_KEY
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import dotenv_values

from cudaquant.config.settings import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://finnhub.io/api/v1"


def _api_key() -> str:
    """Resolve FINNHUB_API_KEY from settings, process env, or the project .env."""
    return (
        getattr(settings, "FINNHUB_API_KEY", None)
        or os.getenv("FINNHUB_API_KEY")
        or dotenv_values().get("FINNHUB_API_KEY")
        or ""
    )


class FinnhubProvider:
    """Finnhub API — news, insider sentiment."""

    def __init__(self):
        self.api_key = _api_key()
        self._client = httpx.Client(timeout=15.0)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a Finnhub endpoint, returning parsed JSON or None on any failure."""
        if not self.api_key:
            return None
        query = dict(params or {})
        query["token"] = self.api_key
        try:
            resp = self._client.get(f"{_BASE_URL}/{path}", params=query)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # network, HTTP, decode errors → degrade gracefully
            logger.warning("Finnhub %s failed: %s", path, e)
            return None

    def get_company_news(self, symbol: str, days_back: int = 7) -> list[dict]:
        """Return news headlines for ``symbol`` over the last ``days_back`` days."""
        symbol = symbol.strip().upper()
        if not symbol:
            return []
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=max(0, days_back))
        data = self._get(
            "company-news",
            {
                "symbol": symbol,
                "from": start.isoformat(),
                "to": today.isoformat(),
            },
        )
        return data if isinstance(data, list) else []

    def get_insider_sentiment(self, symbol: str) -> dict:
        """Return insider sentiment for ``symbol`` (data rows + symbol) or {}."""
        symbol = symbol.strip().upper()
        if not symbol:
            return {}
        data = self._get("stock/insider-sentiment", {"symbol": symbol})
        return data if isinstance(data, dict) else {}

    def close(self) -> None:
        """Release the underlying HTTP client."""
        self._client.close()
