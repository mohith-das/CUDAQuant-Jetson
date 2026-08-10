"""Integration test conftest — isolate from production DB."""
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolate_db_from_production(tmp_path_factory):
    """Redirect all DuckDB operations to a temp directory.

    Prevents tests from locking or corrupting the production
    data/cudaquant.duckdb file. Each session gets a fresh temp DB.
    """
    tmp = tmp_path_factory.mktemp("cudaquant_test")
    db_path = str(tmp / "cudaquant.duckdb")
    os.environ["DUCKDB_PATH"] = db_path
    os.environ["DATA_DIR"] = str(tmp)
    yield
    # Cleanup happens via tmp_path_factory
