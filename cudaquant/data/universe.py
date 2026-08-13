"""Named symbol universes (watchlists) with DuckDB persistence.

A ``Universe`` is an ordered-free, deduped set of symbols (the system is
single-user, so no ownership column). Real database errors propagate to the
caller (fail loud); only missing rows in mutating methods raise ``KeyError``.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from cudaquant.config.settings import settings


@dataclass
class Universe:
    """A named set of symbols (watchlist)."""

    id: str
    name: str
    symbols: list[str]
    created_at: str
    updated_at: str


def _normalize_symbols(symbols: list[str]) -> list[str]:
    """Strip, upper-case, dedupe, and sort symbols."""
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        value = str(symbol).strip().upper()
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return sorted(normalized)


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string (mirrors experiment timestamps)."""
    return datetime.now(timezone.utc).isoformat()


class UniverseStore:
    """DuckDB-backed CRUD for ``Universe`` rows (watchlists)."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(settings.DUCKDB_PATH)
        self._init_db()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        path = Path(self._db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(path))

    def _init_db(self) -> None:
        con = self._connect()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS universes (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    symbols JSON,
                    created_at VARCHAR,
                    updated_at VARCHAR
                )
                """
            )
        finally:
            con.close()

    @staticmethod
    def _row_to_universe(row: tuple) -> Universe:
        return Universe(
            id=row[0],
            name=row[1],
            symbols=json.loads(row[2]) if row[2] else [],
            created_at=row[3],
            updated_at=row[4],
        )

    def _save(self, universe: Universe) -> None:
        con = self._connect()
        try:
            con.execute(
                "INSERT OR REPLACE INTO universes VALUES (?, ?, ?, ?, ?)",
                [
                    universe.id,
                    universe.name,
                    json.dumps(universe.symbols),
                    universe.created_at,
                    universe.updated_at,
                ],
            )
        finally:
            con.close()

    def create(self, name: str, symbols: list[str]) -> Universe:
        """Create and persist a new universe, returning it."""
        now = _now_iso()
        universe = Universe(
            id=str(uuid.uuid4())[:8],
            name=str(name or "").strip(),
            symbols=_normalize_symbols(symbols),
            created_at=now,
            updated_at=now,
        )
        self._save(universe)
        return universe

    def get(self, id: str) -> Universe | None:
        """Return the universe with ``id`` or None."""
        con = self._connect()
        try:
            row = con.execute("SELECT * FROM universes WHERE id = ?", [id]).fetchone()
        finally:
            con.close()
        return self._row_to_universe(row) if row else None

    def list_all(self) -> list[Universe]:
        """Return all universes ordered by creation time then id."""
        con = self._connect()
        try:
            rows = con.execute("SELECT * FROM universes ORDER BY created_at, id").fetchall()
        finally:
            con.close()
        return [self._row_to_universe(row) for row in rows]

    def update(
        self,
        id: str,
        name: str | None = None,
        symbols: list[str] | None = None,
    ) -> Universe:
        """Update ``name`` and/or ``symbols`` of an existing universe."""
        existing = self.get(id)
        if existing is None:
            raise KeyError(f"Universe not found: {id}")
        updated = Universe(
            id=existing.id,
            name=str(name or "").strip() if name is not None else existing.name,
            symbols=_normalize_symbols(symbols) if symbols is not None else existing.symbols,
            created_at=existing.created_at,
            updated_at=_now_iso(),
        )
        self._save(updated)
        return updated

    def add_symbols(self, id: str, symbols: list[str]) -> Universe:
        """Merge new symbols into an existing universe (idempotent)."""
        existing = self.get(id)
        if existing is None:
            raise KeyError(f"Universe not found: {id}")
        merged = sorted(set(existing.symbols) | set(_normalize_symbols(symbols)))
        return self.update(id, symbols=merged)

    def remove_symbol(self, id: str, symbol: str) -> Universe:
        """Remove one symbol from an existing universe."""
        existing = self.get(id)
        if existing is None:
            raise KeyError(f"Universe not found: {id}")
        target = str(symbol or "").strip().upper()
        remaining = [s for s in existing.symbols if s != target]
        return self.update(id, symbols=remaining)

    def delete(self, id: str) -> None:
        """Delete a universe (no-op if it does not exist)."""
        con = self._connect()
        try:
            con.execute("DELETE FROM universes WHERE id = ?", [id])
        finally:
            con.close()


# ── Shared singleton ─────────────────────────────────────────────────────────
# Mirrors get_shared_engine: API routes and callbacks see the same store.

_shared_universe: UniverseStore | None = None


def get_shared_universe(db_path: str | None = None) -> UniverseStore:
    """Return the shared UniverseStore singleton for the given db_path."""
    global _shared_universe
    if _shared_universe is None:
        _shared_universe = UniverseStore(db_path=db_path)
    return _shared_universe
