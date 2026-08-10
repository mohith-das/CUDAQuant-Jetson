"""DuckDB-backed cache for web research tool results with TTL expiry.

Stores search/scrape results as JSON strings keyed by ``(tool, query)``.
Entries expire after ``ttl_seconds``; expired rows are treated as cache
misses by :meth:`SearchCache.get` and removed by :meth:`SearchCache.clear_expired`.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_cache (
    tool VARCHAR NOT NULL,
    query VARCHAR NOT NULL,
    result_json VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (tool, query)
)
"""


class SearchCache:
    """Cache for search/scrape results keyed by (tool, query), with TTL."""

    def __init__(self, db_path: str, ttl_seconds: int = 3600):
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(db_path)
        self._conn.execute(_SCHEMA)

    def get(self, tool: str, query: str) -> str | None:
        """Return the cached JSON string, or None if missing/expired."""
        row = self._conn.execute(
            "SELECT result_json, created_at FROM search_cache WHERE tool = ? AND query = ?",
            [tool, query],
        ).fetchone()
        if row is None:
            return None
        result_json, created_at = row
        if created_at is None:
            return result_json
        age_seconds = (datetime.utcnow() - created_at).total_seconds()
        if age_seconds > self.ttl_seconds:
            return None
        return result_json

    def set(self, tool: str, query: str, result_json: str) -> None:
        """Upsert a result for (tool, query), refreshing its timestamp."""
        self._conn.execute(
            "INSERT OR REPLACE INTO search_cache (tool, query, result_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            [tool, query, result_json, datetime.utcnow()],
        )

    def clear_expired(self) -> int:
        """Delete expired rows; returns the number of rows removed."""
        before = self._conn.execute("SELECT count(*) FROM search_cache").fetchone()[0]
        cutoff = datetime.utcnow() - timedelta(seconds=self.ttl_seconds)
        self._conn.execute("DELETE FROM search_cache WHERE created_at < ?", [cutoff])
        after = self._conn.execute("SELECT count(*) FROM search_cache").fetchone()[0]
        return before - after

    def close(self) -> None:
        """Close the underlying DuckDB connection."""
        self._conn.close()

    def __enter__(self) -> "SearchCache":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
