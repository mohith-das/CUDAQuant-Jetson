"""Financial Modeling Prep (FMP) API client — fundamentals, statements, earnings.

Reads the API key from settings/env (``FMP_API_KEY``); returns empty results on
any error so callers can degrade gracefully (no key, network failure, bad
symbol, HTTP error, or non-JSON response).

Uses the current ``/stable/`` API. FMP decommissioned the legacy ``/api/v3/``
endpoints for non-legacy accounts after 2025-08-31, so v3 paths 403 here.

Environment: FMP_API_KEY
"""

import logging
import os
from typing import Any

import httpx
from dotenv import dotenv_values

from cudaquant.config.settings import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://financialmodelingprep.com/stable"


def _api_key() -> str:
    """Resolve FMP_API_KEY from settings, process env, or the project .env."""
    return (
        getattr(settings, "FMP_API_KEY", None)
        or os.getenv("FMP_API_KEY")
        or dotenv_values().get("FMP_API_KEY")
        or ""
    )


class FMPProvider:
    """FMP API — fundamentals, financial statements, earnings."""

    def __init__(self):
        self.api_key = _api_key()
        self._client = httpx.Client(timeout=15.0)

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

    def get_income_statement(self, symbol: str, limit: int = 4) -> list[dict]:
        """Return the last ``limit`` annual income statements for ``symbol``."""
        symbol = symbol.strip().upper()
        if not symbol:
            return []
        data = self._get("income-statement", {"symbol": symbol, "limit": limit})
        return data if isinstance(data, list) else []

    def get_balance_sheet(self, symbol: str, limit: int = 4) -> list[dict]:
        """Return the last ``limit`` annual balance sheets for ``symbol``."""
        symbol = symbol.strip().upper()
        if not symbol:
            return []
        data = self._get(
            "balance-sheet-statement", {"symbol": symbol, "limit": limit}
        )
        return data if isinstance(data, list) else []

    def get_key_metrics(self, symbol: str) -> list[dict]:
        """Return key financial metrics for ``symbol`` (annual rows)."""
        symbol = symbol.strip().upper()
        if not symbol:
            return []
        data = self._get("key-metrics", {"symbol": symbol})
        return data if isinstance(data, list) else []

    def get_profile(self, symbol: str) -> dict:
        """Return the company profile for ``symbol`` (first match or {})."""
        symbol = symbol.strip().upper()
        if not symbol:
            return {}
        data = self._get("profile", {"symbol": symbol})
        if isinstance(data, list) and data:
            return data[0]
        return {}

    def close(self) -> None:
        """Release the underlying HTTP client."""
        self._client.close()
