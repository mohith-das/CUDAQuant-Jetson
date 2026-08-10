"""DuckDB connection manager for CUDAQuant-Jetson."""
from pathlib import Path

import duckdb

from cudaquant.config.settings import settings

_wal_configured = False


def _ensure_wal() -> None:
    """Enable WAL mode on the database so concurrent readers don't block."""
    global _wal_configured
    if _wal_configured:
        return
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # WAL must be set on a write connection before any other connections open
    con = duckdb.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.close()
    _wal_configured = True


def get_db_path() -> Path:
    """Resolve the DuckDB file path from settings."""
    return Path(settings.DUCKDB_PATH)


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, creating the data directory if needed.

    Args:
        read_only: If True, opens in read-only mode (safe for concurrent
                   readers — won't contend with the live server's write lock).

    The parent directory of the database file is created on demand so the
    connection can be opened before any explicit setup step.
    """
    _ensure_wal()
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)
