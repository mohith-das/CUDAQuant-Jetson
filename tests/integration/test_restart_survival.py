"""Restart-survival tests — prove writes persist to DuckDB.

These tests construct ExperimentEngine/ModelRegistry with explicit db_path
to bypass the Settings singleton and avoid cross-test env contamination.
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def test_db(monkeypatch):
    """Isolated temp DuckDB — sets DUCKDB_PATH env so ExperimentEngine finds it."""
    tmp = Path(tempfile.mkdtemp(prefix="cudaquant_test_"))
    db_path = str(tmp / "cudaquant.duckdb")
    monkeypatch.setenv("DUCKDB_PATH", db_path)
    monkeypatch.setenv("DATA_DIR", str(tmp))
    yield db_path
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


class TestPersistence:
    """Prove that writes survive by checking DuckDB directly."""

    def test_experiment_engine_persists_to_duckdb(self, test_db):
        """ExperimentEngine.propose() writes to DuckDB — not just in-memory."""
        from cudaquant.experiments.engine import ExperimentEngine, ExperimentOrigin

        engine = ExperimentEngine(db_path=test_db)
        exp = engine.propose(hypothesis="persistence test", origin=ExperimentOrigin.MANUAL)
        exp_id = exp.experiment_id

        # Verify in same engine instance (in-memory)
        assert engine.get(exp_id) is not None

        # Verify in DuckDB directly (the real test)
        import duckdb
        con = duckdb.connect(test_db, read_only=True)
        rows = con.execute(
            "SELECT experiment_id, hypothesis FROM experiments WHERE experiment_id = ?",
            [exp_id],
        ).fetchall()
        con.close()
        assert len(rows) == 1, f"Experiment NOT in DuckDB! DB={test_db}, rows={rows}"
        assert rows[0][1] == "persistence test"

    def test_experiment_survives_new_instance(self, test_db):
        """Different ExperimentEngine instance sees the same persisted data."""
        from cudaquant.experiments.engine import ExperimentEngine, ExperimentOrigin

        # Write with instance 1
        e1 = ExperimentEngine(db_path=test_db)
        exp = e1.propose(hypothesis="survives restart", origin=ExperimentOrigin.MANUAL)
        exp_id = exp.experiment_id

        # Read with instance 2 (simulates process restart)
        e2 = ExperimentEngine(db_path=test_db)
        found = e2.get(exp_id)
        assert found is not None, f"Experiment NOT found by second instance! exp_id={exp_id}"
        assert found.hypothesis == "survives restart"

    def test_model_registry_persists_to_duckdb(self, test_db):
        """ModelRegistry.register() writes to DuckDB."""
        from cudaquant.ml.registry import ModelRecord, ModelRegistry, ModelStatus

        reg1 = ModelRegistry(db_path=test_db)
        reg1.register(ModelRecord(
            model_id="persist_model",
            family="lr",
            status=ModelStatus.CANDIDATE,
        ))

        # Verify in DuckDB
        import duckdb
        con = duckdb.connect(test_db, read_only=True)
        rows = con.execute(
            "SELECT model_id FROM model_registry WHERE model_id = ?",
            ["persist_model"],
        ).fetchall()
        con.close()
        assert len(rows) == 1, f"Model NOT in DuckDB! rows={rows}"

    def test_model_survives_new_instance(self, test_db):
        """Different ModelRegistry instance loads persisted data."""
        from cudaquant.ml.registry import ModelRecord, ModelRegistry, ModelStatus

        reg1 = ModelRegistry(db_path=test_db)
        reg1.register(ModelRecord(
            model_id="survive_model",
            family="lr",
            status=ModelStatus.CANDIDATE,
        ))

        reg2 = ModelRegistry(db_path=test_db)
        found = reg2.get("survive_model")
        assert found is not None, "Model NOT found by second instance!"
        assert found.model_id == "survive_model"
