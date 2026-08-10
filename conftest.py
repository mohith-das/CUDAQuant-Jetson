"""Root conftest — shared fixtures for all tests."""
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Temporary directory for test data artifacts."""
    with tempfile.TemporaryDirectory(prefix="cudaquant_test_") as tmp:
        yield Path(tmp)


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the project root."""
    return Path(__file__).resolve().parent
