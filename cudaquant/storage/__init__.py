"""Persistence layer — Parquet, DuckDB, SQLite metadata."""
from cudaquant.storage.db import get_connection, get_db_path

__all__ = ["get_connection", "get_db_path"]
