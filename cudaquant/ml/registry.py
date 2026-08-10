"""Model registry for tracking ML models, versions, and status.

Stores metadata in DuckDB/SQLite. Tracks model lineage, training parameters,
metrics, calibration, and champion/challenger status.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ModelStatus(str, Enum):
    CANDIDATE = "candidate"
    CHALLENGER = "challenger"
    CHAMPION = "champion"
    RETIRED = "retired"


@dataclass
class ModelRecord:
    """Metadata record for a trained model."""

    model_id: str
    family: str  # e.g. "logistic_regression", "random_forest"
    version: int = 1
    git_commit: str = ""
    training_start: str = ""  # ISO date
    training_end: str = ""
    feature_schema: list[str] = field(default_factory=list)
    hyperparameters: dict = field(default_factory=dict)
    seed: int = 42
    metrics: dict = field(default_factory=dict)
    calibration: dict = field(default_factory=dict)
    artifact_path: str = ""  # path to serialized model
    parent_id: str | None = None  # lineage: which model this derived from
    status: ModelStatus = ModelStatus.CANDIDATE
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    promoted_at: str | None = None
    retired_at: str | None = None
    notes: str = ""


class ModelRegistry:
    """In-memory model registry with optional DuckDB persistence.

    Tracks the champion/challenger lifecycle:
    candidate → challenger → champion → retired
    """

    def __init__(self, db_path: str | None = None):
        self._models: dict[str, ModelRecord] = {}
        self._db_path = db_path
        if db_path:
            self._init_db()
            self._load_all()

    def _init_db(self) -> None:
        """Initialize registry table if using persistent storage."""
        try:
            import duckdb
            con = duckdb.connect(self._db_path)
            con.execute("""
                CREATE TABLE IF NOT EXISTS model_registry (
                    model_id VARCHAR PRIMARY KEY,
                    family VARCHAR,
                    version INTEGER,
                    git_commit VARCHAR,
                    training_start VARCHAR,
                    training_end VARCHAR,
                    feature_schema JSON,
                    hyperparameters JSON,
                    seed INTEGER,
                    metrics JSON,
                    calibration JSON,
                    artifact_path VARCHAR,
                    parent_id VARCHAR,
                    status VARCHAR,
                    created_at VARCHAR,
                    promoted_at VARCHAR,
                    retired_at VARCHAR,
                    notes VARCHAR
                )
            """)
            con.close()
        except ImportError:
            pass

    def register(self, record: ModelRecord) -> str:
        """Register a new model. Returns model_id."""
        self._models[record.model_id] = record
        self._persist(record)
        return record.model_id

    def get(self, model_id: str) -> ModelRecord | None:
        return self._models.get(model_id)

    def get_champion(self, family: str) -> ModelRecord | None:
        """Get current champion for a model family."""
        champions = [
            m for m in self._models.values()
            if m.family == family and m.status == ModelStatus.CHAMPION
        ]
        return champions[0] if champions else None

    def get_challengers(self, family: str) -> list[ModelRecord]:
        """Get all challengers for a model family."""
        return [
            m for m in self._models.values()
            if m.family == family and m.status == ModelStatus.CHALLENGER
        ]

    def promote_to_challenger(self, model_id: str) -> bool:
        """Promote a candidate to challenger status."""
        model = self._models.get(model_id)
        if model is None or model.status != ModelStatus.CANDIDATE:
            return False
        model.status = ModelStatus.CHALLENGER
        model.promoted_at = datetime.utcnow().isoformat()
        self._persist(model)
        return True

    def promote_to_champion(self, model_id: str) -> bool:
        """Promote a challenger to champion. Retires previous champion."""
        model = self._models.get(model_id)
        if model is None or model.status != ModelStatus.CHALLENGER:
            return False

        # Retire current champion in same family
        current = self.get_champion(model.family)
        if current:
            current.status = ModelStatus.RETIRED
            current.retired_at = datetime.utcnow().isoformat()
            self._persist(current)

        model.status = ModelStatus.CHAMPION
        model.promoted_at = datetime.utcnow().isoformat()
        self._persist(model)
        return True

    def retire(self, model_id: str) -> bool:
        """Retire a model."""
        model = self._models.get(model_id)
        if model is None:
            return False
        model.status = ModelStatus.RETIRED
        model.retired_at = datetime.utcnow().isoformat()
        self._persist(model)
        return True

    def list_by_status(self, status: ModelStatus) -> list[ModelRecord]:
        return [m for m in self._models.values() if m.status == status]

    def list_all(self) -> list[ModelRecord]:
        return list(self._models.values())

    def _persist(self, record: ModelRecord) -> None:
        """Persist to DuckDB if configured."""
        if not self._db_path:
            return
        try:
            import json

            import duckdb
            con = duckdb.connect(self._db_path)
            con.execute("""
                INSERT OR REPLACE INTO model_registry VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, [
                record.model_id, record.family, record.version,
                record.git_commit, record.training_start, record.training_end,
                json.dumps(record.feature_schema),
                json.dumps(record.hyperparameters),
                record.seed,
                json.dumps(record.metrics),
                json.dumps(record.calibration),
                record.artifact_path, record.parent_id,
                record.status.value, record.created_at,
                record.promoted_at, record.retired_at, record.notes,
            ])
            con.close()
        except (ImportError, Exception):
            pass

    def _load_all(self) -> None:
        """Load all models from DuckDB."""
        if not self._db_path:
            return
        import json
        try:
            import duckdb
            con = duckdb.connect(self._db_path)
            rows = con.execute("SELECT * FROM model_registry").fetchall()
            con.close()
            for row in rows:
                record = ModelRecord(
                    model_id=row[0], family=row[1] or "", version=row[2] or 1,
                    git_commit=row[3] or "", training_start=row[4] or "",
                    training_end=row[5] or "",
                    feature_schema=json.loads(row[6]) if row[6] else [],
                    hyperparameters=json.loads(row[7]) if row[7] else {},
                    seed=row[8] or 42,
                    metrics=json.loads(row[9]) if row[9] else {},
                    calibration=json.loads(row[10]) if row[10] else {},
                    artifact_path=row[11] or "", parent_id=row[12],
                    status=ModelStatus(row[13]) if row[13] else ModelStatus.CANDIDATE,
                    created_at=row[14] or "", promoted_at=row[15],
                    retired_at=row[16], notes=row[17] or "",
                )
                self._models[record.model_id] = record
        except (ImportError, Exception):
            pass
