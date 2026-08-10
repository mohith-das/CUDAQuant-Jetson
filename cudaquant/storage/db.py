"""DuckDB connection manager for CUDAQuant-Jetson.

DuckDB uses a single-writer, multi-reader model (NOT SQLite's WAL).
For concurrent access, use ``get_connection(read_only=True)`` for
readers while the live server holds the write connection.
"""

from pathlib import Path

import duckdb

from cudaquant.config.settings import settings


def get_db_path() -> Path:
    """Resolve the DuckDB file path from settings."""
    return Path(settings.DUCKDB_PATH)


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, creating the data directory if needed.

    Args:
        read_only: If True, opens in read-only mode (safe for concurrent
                   readers alongside the live server's write connection).

    Returns a working connection. Raises duckdb.IOException on failure
    (callers should propagate, not silently swallow).
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)
