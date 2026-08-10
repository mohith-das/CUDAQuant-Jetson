"""Root conftest — shared fixtures + test isolation for all tests.

``pytest_configure`` runs before ANY test module is imported, guaranteeing
that env-var overrides land before ``Settings()`` is ever constructed —
regardless of which test file is collected first alphabetically.
"""

import os
import tempfile
from pathlib import Path

import pytest


def pytest_configure(config):
    """Set test-isolated env vars before any test module collection."""
    if "CUDAQUANT_TEST_DB" not in os.environ:
        tmp = Path(tempfile.mkdtemp(prefix="cudaquant_test_"))
        os.environ["DUCKDB_PATH"] = str(tmp / "cudaquant.duckdb")
        os.environ["DATA_DIR"] = str(tmp)
        os.environ["KILL_SWITCH_FILE"] = str(tmp / ".kill_switch")
        os.environ["CUDA_ENABLED"] = "false"
        os.environ["CUDAQUANT_TEST_DB"] = "1"


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Temporary directory for test data artifacts."""
    with tempfile.TemporaryDirectory(prefix="cudaquant_test_") as tmp:
        yield Path(tmp)


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the project root."""
    return Path(__file__).resolve().parent
