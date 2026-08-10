"""Experiment engine for CUDAQuant — tracks hypotheses, runs, and outcomes.

Every experiment is traceable: hypothesis, origin, parameter changes,
metrics, status, and lineage. Supports automated search within budgets.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ExperimentStatus(str, Enum):
    PROPOSED = "proposed"
    QUEUED = "queued"
    RUNNING = "running"
    REJECTED = "rejected"
    BACKTEST_PASSED = "backtest_passed"
    PAPER_CANDIDATE = "paper_candidate"
    PAPER_RUNNING = "paper_running"
    PROBATION = "probation"
    PRODUCTION = "production"
    RETIRED = "retired"
    FAILED = "failed"


class ExperimentOrigin(str, Enum):
    MANUAL = "manual"
    GRID = "grid"
    RANDOM = "random"
    EVOLUTIONARY = "evolutionary"
    HYPERPARAMETER = "hyperparameter"
    LLM = "llm"
    LLM_FALLBACK = "llm_fallback"  # LLM unavailable — used local heuristic instead
    DRIFT = "drift"


@dataclass
class Experiment:
    """A single experiment record."""

    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    hypothesis: str = ""
    origin: ExperimentOrigin = ExperimentOrigin.MANUAL
    parent_id: str | None = None
    changed_parameters: dict = field(default_factory=dict)
    changed_features: list[str] = field(default_factory=list)
    model_family: str = ""
    model_id: str | None = None
    training_window: int = 504  # ~2 years daily
    validation_window: int = 252  # ~1 year
    test_window: int = 252
    cost_model: str = "baseline"
    metrics: dict = field(default_factory=dict)
    result: str = ""
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    commit: str = ""
    seed: int = 42
    backend: str = "cpu"  # cpu | gpu
    runtime_ms: float = 0.0
    notes: str = ""


class ExperimentBudget:
    """Limits on automated experimentation to prevent runaway resource use."""

    def __init__(
        self,
        max_concurrent: int = 2,
        max_per_day: int = 10,
        max_per_weekend: int = 50,
        max_runtime_minutes: int = 120,
        cpu_only_outside_hours: bool = True,
    ):
        self.max_concurrent = max_concurrent
        self.max_per_day = max_per_day
        self.max_per_weekend = max_per_weekend
        self.max_runtime_minutes = max_runtime_minutes
        self.cpu_only_outside_hours = cpu_only_outside_hours
        self._daily_count = 0
        self._running: list[str] = []

    def can_run(self, experiment: Experiment) -> tuple[bool, str]:
        """Check if experiment can be run within budget."""
        if len(self._running) >= self.max_concurrent:
            return False, "max concurrent experiments reached"
        if self._daily_count >= self.max_per_day:
            return False, "daily experiment limit reached"
        return True, "ok"

    def start(self, experiment_id: str) -> None:
        self._running.append(experiment_id)
        self._daily_count += 1

    def finish(self, experiment_id: str) -> None:
        if experiment_id in self._running:
            self._running.remove(experiment_id)

    def reset_daily(self) -> None:
        self._daily_count = 0


class ExperimentEngine:
    """Manages experiment lifecycle, scheduling, and search.

    Supports:
    - Manual experiments (user-defined)
    - Grid search over parameter ranges
    - Random search within bounds
    - Evolutionary mutation of parent experiments
    """

    def __init__(self, budget: ExperimentBudget | None = None, db_path: str | None = None):
        self._experiments: dict[str, Experiment] = {}
        self._queue: list[str] = []
        self.budget = budget or ExperimentBudget()
        self._db_path = db_path
        if db_path:
            self._init_db()
            self._load_all()

    def propose(
        self,
        hypothesis: str,
        origin: ExperimentOrigin = ExperimentOrigin.MANUAL,
        parent_id: str | None = None,
        changed_parameters: dict | None = None,
        **kwargs,
    ) -> Experiment:
        """Create a new experiment proposal."""
        exp = Experiment(
            hypothesis=hypothesis,
            origin=origin,
            parent_id=parent_id,
            changed_parameters=changed_parameters or {},
            **kwargs,
        )
        self._experiments[exp.experiment_id] = exp
        self._persist(exp)
        return exp

    def enqueue(self, experiment_id: str) -> bool:
        """Queue an experiment for execution."""
        exp = self._experiments.get(experiment_id)
        if exp is None:
            return False
        exp.status = ExperimentStatus.QUEUED
        self._queue.append(experiment_id)
        self._persist(exp)
        return True

    def dequeue(self) -> Experiment | None:
        """Get next queued experiment."""
        if not self._queue:
            return None
        exp_id = self._queue.pop(0)
        exp = self._experiments.get(exp_id)
        if exp:
            can_run, reason = self.budget.can_run(exp)
            if not can_run:
                self._queue.insert(0, exp_id)  # put back
                return None
            exp.status = ExperimentStatus.RUNNING
            self.budget.start(exp_id)
        return exp

    def complete(self, experiment_id: str, metrics: dict, result: str, status: ExperimentStatus) -> None:
        """Record experiment completion."""
        exp = self._experiments.get(experiment_id)
        if exp is None:
            return
        exp.metrics = metrics
        exp.result = result
        exp.status = status
        self.budget.finish(experiment_id)
        self._persist(exp)

    def grid_search(
        self,
        base_params: dict,
        param_grid: dict[str, list[Any]],
        hypothesis_template: str,
        **kwargs,
    ) -> list[str]:
        """Generate grid search experiments.

        Args:
            base_params: Base parameter dict.
            param_grid: Dict of {param_name: [values]}.
            hypothesis_template: Template string with {param_name} placeholders.

        Returns:
            List of experiment IDs.
        """
        import itertools

        keys = list(param_grid.keys())
        values = list(param_grid.values())
        experiment_ids = []

        for combo in itertools.product(*values):
            params = {**base_params, **dict(zip(keys, combo, strict=True))}
            hypothesis = hypothesis_template.format(**params)
            exp = self.propose(
                hypothesis=hypothesis,
                origin=ExperimentOrigin.GRID,
                changed_parameters=params,
                **kwargs,
            )
            experiment_ids.append(exp.experiment_id)

        return experiment_ids

    def random_search(
        self,
        base_params: dict,
        param_bounds: dict[str, tuple[Any, Any]],
        n: int = 20,
        seed: int = 42,
        **kwargs,
    ) -> list[str]:
        """Generate random search experiments.

        Args:
            base_params: Base parameter dict.
            param_bounds: Dict of {param_name: (low, high)}.
            n: Number of random experiments.
            seed: Random seed.

        Returns:
            List of experiment IDs.
        """
        import numpy as np

        rng = np.random.default_rng(seed)
        experiment_ids = []

        for _ in range(n):
            params = dict(base_params)
            for name, (low, high) in param_bounds.items():
                if isinstance(low, int) and isinstance(high, int):
                    params[name] = int(rng.integers(low, high + 1))
                elif isinstance(low, float) or isinstance(high, float):
                    params[name] = float(rng.uniform(low, high))

            exp = self.propose(
                hypothesis=f"random_search_{len(experiment_ids)}",
                origin=ExperimentOrigin.RANDOM,
                changed_parameters=params,
                seed=seed + len(experiment_ids),
                **kwargs,
            )
            experiment_ids.append(exp.experiment_id)

        return experiment_ids

    def mutate(
        self,
        parent_id: str,
        mutation_rate: float = 0.2,
        param_bounds: dict[str, tuple[Any, Any]] | None = None,
    ) -> Experiment | None:
        """Create a mutation of a parent experiment.

        Perturbs parameters slightly to explore neighborhood.
        """
        parent = self._experiments.get(parent_id)
        if parent is None:
            return None

        import numpy as np
        rng = np.random.default_rng()

        new_params = dict(parent.changed_parameters)
        bounds = param_bounds or {}
        for name in new_params:
            if rng.random() < mutation_rate and name in bounds:
                low, high = bounds[name]
                current = new_params[name]
                perturbation = (high - low) * 0.1 * rng.normal()
                new_params[name] = max(low, min(high, current + perturbation))
                if isinstance(current, int):
                    new_params[name] = int(new_params[name])

        return self.propose(
            hypothesis=f"mutation_of_{parent_id}",
            origin=ExperimentOrigin.EVOLUTIONARY,
            parent_id=parent_id,
            changed_parameters=new_params,
        )

    def get(self, experiment_id: str) -> Experiment | None:
        return self._experiments.get(experiment_id)

    def list_by_status(self, status: ExperimentStatus) -> list[Experiment]:
        return [e for e in self._experiments.values() if e.status == status]

    def list_all(self) -> list[Experiment]:
        return list(self._experiments.values())

    def queue_size(self) -> int:
        return len(self._queue)

    def running_count(self) -> int:
        return len(self.budget._running)

    # ── DuckDB persistence ──────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create experiments table if it doesn't exist."""
        import os

        import duckdb

        from cudaquant.config.settings import settings
        try:
            db_path = self._db_path or settings.DUCKDB_PATH
            os.makedirs(os.path.dirname(str(db_path)), exist_ok=True)
            con = duckdb.connect(str(db_path))
            con.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id VARCHAR PRIMARY KEY,
                    created_at VARCHAR,
                    hypothesis VARCHAR,
                    origin VARCHAR,
                    parent_id VARCHAR,
                    changed_parameters JSON,
                    changed_features JSON,
                    model_family VARCHAR,
                    model_id VARCHAR,
                    training_window INTEGER,
                    validation_window INTEGER,
                    test_window INTEGER,
                    cost_model VARCHAR,
                    metrics JSON,
                    result VARCHAR,
                    status VARCHAR,
                    commit VARCHAR,
                    seed INTEGER,
                    backend VARCHAR,
                    runtime_ms DOUBLE,
                    notes VARCHAR
                )
            """)
            con.close()
        except ImportError:
            logger.info("duckdb not available — ExperimentEngine running in-memory only")
        except Exception as e:
            logger.error("Experiment DB init failed: %s", e, exc_info=True)
            raise

    def _persist(self, exp: Experiment) -> None:
        """Save one experiment to DuckDB."""
        if not self._db_path:
            return
        import json

        import duckdb
        try:
            con = duckdb.connect(str(self._db_path))
            con.execute("""
                INSERT OR REPLACE INTO experiments VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, [
                exp.experiment_id, exp.created_at, exp.hypothesis,
                exp.origin.value, exp.parent_id,
                json.dumps(exp.changed_parameters),
                json.dumps(exp.changed_features),
                exp.model_family, exp.model_id,
                exp.training_window, exp.validation_window, exp.test_window,
                exp.cost_model,
                json.dumps(exp.metrics),
                exp.result, exp.status.value,
                exp.commit, exp.seed, exp.backend,
                exp.runtime_ms, exp.notes,
            ])
            con.close()
        except ImportError:
            logger.debug("duckdb not available — experiment persist skipped")
        except Exception as e:
            logger.error("Experiment persist failed: %s", e, exc_info=True)
            raise

    def _load_all(self) -> None:
        """Load all experiments from DuckDB."""
        if not self._db_path:
            return
        import json

        import duckdb
        try:
            con = duckdb.connect(str(self._db_path))
            rows = con.execute("SELECT * FROM experiments").fetchall()
            con.close()
            for row in rows:
                exp = Experiment(
                    experiment_id=row[0], created_at=row[1], hypothesis=row[2],
                    origin=ExperimentOrigin(row[3]), parent_id=row[4],
                    changed_parameters=json.loads(row[5]) if row[5] else {},
                    changed_features=json.loads(row[6]) if row[6] else [],
                    model_family=row[7] or "", model_id=row[8],
                    training_window=row[9] or 504,
                    validation_window=row[10] or 252,
                    test_window=row[11] or 252,
                    cost_model=row[12] or "baseline",
                    metrics=json.loads(row[13]) if row[13] else {},
                    result=row[14] or "",
                    status=ExperimentStatus(row[15]) if row[15] else ExperimentStatus.PROPOSED,
                    commit=row[16] or "", seed=row[17] or 42,
                    backend=row[18] or "cpu",
                    runtime_ms=float(row[19]) if row[19] else 0.0,
                    notes=row[20] or "",
                )
                self._experiments[exp.experiment_id] = exp
        except ImportError:
            logger.debug("duckdb not available — experiment load skipped")
        except Exception as e:
            logger.error("Experiment load failed: %s", e, exc_info=True)
            raise


# ── Shared singleton ─────────────────────────────────────────────────────────
# Used by both API routes and scheduler callbacks to avoid cross-instance
# staleness (each caller sees the same DB state).

_shared_engine: ExperimentEngine | None = None


def get_shared_engine(db_path: str) -> ExperimentEngine:
    """Return the shared ExperimentEngine singleton for the given db_path."""
    global _shared_engine
    if _shared_engine is None:
        _shared_engine = ExperimentEngine(db_path=db_path)
    return _shared_engine
