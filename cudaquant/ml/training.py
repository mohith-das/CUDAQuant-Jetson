"""Training studio service — orchestrates model training runs.

Each TrainingRun fetches synthetic bars, builds a minimal feature matrix,
trains a time-series model family, evaluates it, and registers the resulting
candidate model in the ModelRegistry. Runs are persisted to a DuckDB
`training_runs` table with a queued -> running -> completed/failed lifecycle.
"""

import json
import logging
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, cast

import duckdb
import numpy as np

from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator
from cudaquant.ml.models import (
    TSLogisticRegression,
    TSRandomForest,
    evaluate_classifier,
    prepare_targets,
)
from cudaquant.ml.registry import (
    ModelRecord,
    ModelRegistry,
    ModelStatus,
    get_shared_registry,
)

logger = logging.getLogger(__name__)

_MODEL_FAMILIES = ("logistic_regression", "random_forest")
_RUN_STATUSES = ("queued", "running", "completed", "failed")

_ModelFamily = Literal["logistic_regression", "random_forest"]
_RunStatus = Literal["queued", "running", "completed", "failed"]


def _close_to_close_returns(close: np.ndarray) -> np.ndarray:
    """Close-to-close simple returns; first bar has no history (0.0)."""
    returns = np.zeros_like(close)
    returns[1:] = np.diff(close) / close[:-1]
    return returns


def _close_to_close_log_returns(close: np.ndarray) -> np.ndarray:
    """Close-to-close log returns; first bar has no history (0.0)."""
    returns = np.zeros_like(close)
    returns[1:] = np.log(close[1:] / close[:-1])
    return returns


# Minimal feature set, all computed from current/past closes only (no
# look-ahead). Matches the feature pattern in api/app.py retrain_callback.
_FEATURE_FUNCS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "returns": _close_to_close_returns,
    "log_returns": _close_to_close_log_returns,
}


@dataclass
class TrainingRun:
    """A single model training run record."""

    id: str
    universe_id: str | None
    symbols: list[str]
    model_family: _ModelFamily
    features: list[str]
    horizon: int
    created_at: str
    status: _RunStatus
    metrics: dict | None = None
    model_id: str | None = None
    error: str | None = None


class TrainingService:
    """Runs model training jobs and persists their lifecycle to DuckDB."""

    def __init__(self, db_path: str | None = None, registry: ModelRegistry | None = None):
        self._db_path = db_path
        self._registry = registry or ModelRegistry(db_path=db_path)
        self._runs: dict[str, TrainingRun] = {}
        if db_path:
            self._init_db()

    # ── Public API ──────────────────────────────────────────────────────────

    def run(
        self,
        symbols: str | list[str],
        model_family: str,
        features: list[str] | None = None,
        horizon: int = 5,
        universe_id: str | None = None,
    ) -> TrainingRun:
        """Train a model synchronously and record the run lifecycle.

        Validation errors raise ValueError (client errors fail loud before a
        run row is created). Training/runtime errors mark the run failed with
        the error string and the run is returned so callers can inspect it.
        """
        symbols = self._validate_symbols(symbols)
        self._validate_model_family(model_family)
        features = self._validate_features(features)
        self._validate_horizon(horizon)

        run = TrainingRun(
            id=uuid.uuid4().hex[:8],
            universe_id=universe_id,
            symbols=symbols,
            model_family=cast(_ModelFamily, model_family),
            features=features,
            horizon=horizon,
            created_at=datetime.now(timezone.utc).isoformat(),
            status="queued",
        )
        self._persist(run)

        run.status = "running"
        self._persist(run)

        try:
            x_mat, y_t = self._build_training_matrix(symbols, features, horizon)
            model_id, metrics = self._train_and_register(
                run.id, x_mat, y_t, model_family, features, symbols, horizon
            )
            run.model_id = model_id
            run.metrics = metrics
            run.status = "completed"
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            logger.error("TrainingRun %s failed: %s", run.id, exc, exc_info=True)

        self._persist(run)
        return run

    def get(self, run_id: str) -> TrainingRun | None:
        """Return a run by id, or None if it doesn't exist."""
        if not self._db_path:
            return self._runs.get(run_id)
        con = duckdb.connect(str(self._db_path))
        try:
            row = con.execute(
                "SELECT * FROM training_runs WHERE id = ?", [run_id]
            ).fetchone()
        finally:
            con.close()
        return self._row_to_run(row) if row else None

    def list_all(self, limit: int = 50) -> list[TrainingRun]:
        """Return the most recent runs, newest first."""
        if not self._db_path:
            return list(self._runs.values())[-limit:][::-1]
        con = duckdb.connect(str(self._db_path))
        try:
            rows = con.execute(
                "SELECT * FROM training_runs ORDER BY created_at DESC LIMIT ?",
                [limit],
            ).fetchall()
        finally:
            con.close()
        return [self._row_to_run(row) for row in rows]

    def list_by_status(self, status: str) -> list[TrainingRun]:
        """Return runs in the given status, newest first."""
        if status not in _RUN_STATUSES:
            raise ValueError(
                f"invalid status {status!r}; expected one of {sorted(_RUN_STATUSES)}"
            )
        if not self._db_path:
            return [r for r in self._runs.values() if r.status == status][::-1]
        con = duckdb.connect(str(self._db_path))
        try:
            rows = con.execute(
                "SELECT * FROM training_runs WHERE status = ? ORDER BY created_at DESC",
                [status],
            ).fetchall()
        finally:
            con.close()
        return [self._row_to_run(row) for row in rows]

    # ── Training pipeline ───────────────────────────────────────────────────

    def _build_training_matrix(
        self, symbols: list[str], features: list[str], horizon: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Fetch bars and build the pooled feature matrix + targets.

        Features and targets are computed per symbol from closes only (no
        look-ahead beyond close[i + horizon]); rows from all symbols are
        pooled for the single-fit baseline.
        """
        gen = SyntheticDataGenerator(seed=42)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=60)
        bars = gen.generate_bars(symbols, start, end, BarFrequency.MINUTE_5)
        if bars.empty or "symbol" not in bars.columns:
            raise ValueError("no usable bars for the requested symbols")

        x_parts: list[np.ndarray] = []
        y_parts: list[np.ndarray] = []
        for symbol in symbols:
            sym = bars[bars["symbol"] == symbol].sort_values("timestamp")
            if len(sym) < horizon + 2:
                continue
            close = sym["close"].values.astype(np.float64)
            cols = [_FEATURE_FUNCS[name](close) for name in features]
            x_parts.append(np.column_stack(cols))
            y_parts.append(prepare_targets(sym, horizon=horizon))

        if not x_parts:
            raise ValueError("no usable bars for the requested symbols")
        x_mat = np.vstack(x_parts)
        y_t = np.concatenate(y_parts)
        # First bar has no history; mask infinities from degenerate closes.
        return np.nan_to_num(x_mat, nan=0.0, posinf=0.0, neginf=0.0), y_t

    def _train_and_register(
        self,
        run_id: str,
        x_mat: np.ndarray,
        y_t: np.ndarray,
        model_family: str,
        features: list[str],
        symbols: list[str],
        horizon: int,
    ) -> tuple[str, dict]:
        """Fit the model on valid samples, evaluate, and register a candidate."""
        valid = ~(np.isnan(x_mat).any(axis=1) | np.isnan(y_t))
        n_valid = int(valid.sum())
        if n_valid < 10 or len(np.unique(y_t[valid])) < 2:
            raise ValueError(
                "insufficient valid samples after target alignment: "
                f"{n_valid} (need >= 10 with both classes)"
            )

        if model_family == "logistic_regression":
            model = TSLogisticRegression()
        else:
            model = TSRandomForest()
        model.fit(x_mat, y_t, feature_names=features)

        y_true = y_t[valid]
        y_prob = model.predict_proba(x_mat[valid])
        metrics = evaluate_classifier(y_true, y_prob)

        now = datetime.now(timezone.utc).isoformat()
        record = ModelRecord(
            model_id=f"tr_{run_id}",
            family=model_family,
            training_start=now,
            training_end=now,
            feature_schema=features,
            hyperparameters={"horizon": horizon, "n_symbols": len(symbols)},
            seed=42,
            metrics=metrics,
            status=ModelStatus.CANDIDATE,
            notes=f"symbols={','.join(symbols)}",
        )
        self._registry.register(record)
        return record.model_id, metrics

    # ── Validation ──────────────────────────────────────────────────────────

    def _validate_symbols(self, symbols: str | list[str]) -> list[str]:
        if isinstance(symbols, str):
            symbols = [symbols]
        symbols = list(dict.fromkeys(symbols))  # dedupe, preserve order
        if not symbols or not all(isinstance(s, str) and s.strip() for s in symbols):
            raise ValueError("symbols must be a non-empty list of non-empty strings")
        return symbols

    def _validate_model_family(self, model_family: str) -> None:
        if model_family not in _MODEL_FAMILIES:
            raise ValueError(
                f"invalid model_family {model_family!r}; "
                f"expected one of {sorted(_MODEL_FAMILIES)}"
            )

    def _validate_features(self, features: list[str] | None) -> list[str]:
        features = list(features) if features else ["returns"]
        if not all(isinstance(f, str) and f.strip() for f in features):
            raise ValueError("features must be a list of non-empty strings")
        unknown = [f for f in features if f not in _FEATURE_FUNCS]
        if unknown:
            raise ValueError(
                f"unsupported features {unknown}; supported: {sorted(_FEATURE_FUNCS)}"
            )
        return features

    def _validate_horizon(self, horizon: int) -> None:
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
            raise ValueError("horizon must be an int >= 1")

    # ── DuckDB persistence ──────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create the training_runs table if it doesn't exist."""
        os.makedirs(os.path.dirname(str(self._db_path)) or ".", exist_ok=True)
        con = duckdb.connect(str(self._db_path))
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS training_runs (
                    id VARCHAR PRIMARY KEY,
                    universe_id VARCHAR,
                    symbols JSON,
                    model_family VARCHAR,
                    features JSON,
                    horizon INTEGER,
                    status VARCHAR,
                    metrics JSON,
                    model_id VARCHAR,
                    error VARCHAR,
                    created_at VARCHAR
                )
                """
            )
        finally:
            con.close()

    def _persist(self, run: TrainingRun) -> None:
        """Save one run to DuckDB (or in-memory dict when db_path is None)."""
        if not self._db_path:
            self._runs[run.id] = run
            return
        con = duckdb.connect(str(self._db_path))
        try:
            con.execute(
                """
                INSERT OR REPLACE INTO training_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run.id,
                    run.universe_id,
                    json.dumps(run.symbols),
                    run.model_family,
                    json.dumps(run.features),
                    run.horizon,
                    run.status,
                    json.dumps(run.metrics) if run.metrics is not None else None,
                    run.model_id,
                    run.error,
                    run.created_at,
                ],
            )
        finally:
            con.close()

    def _row_to_run(self, row: tuple[object, ...]) -> TrainingRun:
        """Convert a DuckDB row tuple back into a TrainingRun."""
        if row[6] not in _RUN_STATUSES:
            raise ValueError(f"corrupt training_runs row: unknown status {row[6]!r}")
        return TrainingRun(
            id=row[0],  # type: ignore[arg-type]
            universe_id=row[1],  # type: ignore[arg-type]
            symbols=json.loads(row[2]) if row[2] else [],  # type: ignore[arg-type]
            model_family=cast(_ModelFamily, row[3]),
            features=json.loads(row[4]) if row[4] else [],  # type: ignore[arg-type]
            horizon=row[5],  # type: ignore[arg-type]
            status=cast(_RunStatus, row[6]),
            metrics=json.loads(row[7]) if row[7] else None,  # type: ignore[arg-type]
            model_id=row[8],  # type: ignore[arg-type]
            error=row[9],  # type: ignore[arg-type]
            created_at=row[10],  # type: ignore[arg-type]
        )


# ── Shared singleton ─────────────────────────────────────────────────────────
# Used by both API routes and scheduler callbacks to avoid cross-instance
# staleness — same pattern as ExperimentEngine / ModelRegistry singletons.

_shared_training_service: TrainingService | None = None


def get_shared_training_service(db_path: str) -> TrainingService:
    """Return the shared TrainingService singleton for the given db_path."""
    global _shared_training_service
    if _shared_training_service is None:
        _shared_training_service = TrainingService(
            db_path=db_path, registry=get_shared_registry(db_path)
        )
    return _shared_training_service
