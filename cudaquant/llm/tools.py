"""Thin HTTP clients for LLM research web tools (Brave Search, Tavily, Firecrawl).

Each tool degrades gracefully: if its API key is not configured in settings,
or the upstream call fails/times out, the tool logs the reason and returns an
empty result instead of raising. Results are plain dicts / strings so callers
never depend on provider-specific response shapes.

Keys are read from ``cudaquant.config.settings`` (env / .env). Nothing here
touches trading, risk, or kill-switch state — these are advisory research tools.
"""

import logging

import httpx

from cudaquant.config.settings import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15.0
USER_AGENT = "cudaquant-llm-research/0.1"


def _key_configured(api_key: str | None, tool_name: str) -> bool:
    """Return True if the key is set; otherwise log and return False."""
    if api_key:
        return True
    logger.warning("%s API key not configured — returning empty result", tool_name)
    return False


class BraveSearchTool:
    """Web search via the Brave Search API (https://api.search.brave.com)."""

    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self):
        self.api_key = settings.BRAVE_SEARCH_API_KEY

    def search(self, query: str, count: int = 5) -> list[dict]:
        """Return ``[{"title", "url", "description"}]`` or ``[]`` on failure."""
        if not _key_configured(self.api_key, "Brave"):
            return []
        if not query.strip():
            return []
        count = max(1, count)
        try:
            response = httpx.get(
                self.BASE_URL,
                params={"q": query, "count": count},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self.api_key,
                    "User-Agent": USER_AGENT,
                },
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.warning("Brave search failed for query=%r: %s", query, e)
            return []
        results = payload.get("web", {}).get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", ""),
            }
            for r in results[:count]
            if isinstance(r, dict)
        ]


class TavilySearchTool:
    """Web search via the Tavily Search API (https://api.tavily.com)."""

    BASE_URL = "https://api.tavily.com/search"

    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Return ``[{"title", "url", "content"}]`` or ``[]`` on failure."""
        if not _key_configured(self.api_key, "Tavily"):
            return []
        if not query.strip():
            return []
        max_results = max(1, max_results)
        try:
            response = httpx.post(
                self.BASE_URL,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.warning("Tavily search failed for query=%r: %s", query, e)
            return []
        results = payload.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            }
            for r in results[:max_results]
            if isinstance(r, dict)
        ]


class FirecrawlTool:
    """URL scraping via the Firecrawl API (https://api.firecrawl.dev)."""

    BASE_URL = "https://api.firecrawl.dev/v1/scrape"

    def __init__(self):
        self.api_key = settings.FIRECRAWL_API_KEY

    def scrape(self, url: str) -> str:
        """Return the page's markdown content, or ``""`` on failure."""
        if not _key_configured(self.api_key, "Firecrawl"):
            return ""
        if not url.strip():
            return ""
        try:
            response = httpx.post(
                self.BASE_URL,
                json={"url": url},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": USER_AGENT,
                },
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.warning("Firecrawl scrape failed for url=%r: %s", url, e)
            return ""
        if not payload.get("success", False):
            logger.warning("Firecrawl scrape returned success=false for url=%r", url)
            return ""
        data = payload.get("data", {})
        if not isinstance(data, dict):
            return ""
        return data.get("markdown", "") or ""
