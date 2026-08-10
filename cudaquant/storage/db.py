"""DuckDB connection manager for CUDAQuant-Jetson."""
from pathlib import Path

import duckdb

from cudaquant.config.settings import settings


def get_db_path() -> Path:
    """Resolve the DuckDB file path from settings."""
    return Path(settings.DUCKDB_PATH)


def get_connection() -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, creating the data directory if needed.

    The parent directory of the database file is created on demand so the
    connection can be opened before any explicit setup step.
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))
