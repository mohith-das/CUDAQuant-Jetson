"""Experiment API routes — full CRUD over persistent ExperimentEngine."""
from fastapi import APIRouter, Depends, HTTPException

from cudaquant.api.auth import require_auth
from cudaquant.config.settings import settings
from cudaquant.experiments.engine import (
    ExperimentEngine,
    ExperimentOrigin,
)

router = APIRouter(prefix="/api/experiments", tags=["experiments"], dependencies=[Depends(require_auth)])

# Singleton engine with persistence
_engine = ExperimentEngine(db_path=settings.DUCKDB_PATH)


@router.post("/propose")
def propose_experiment(payload: dict):
    """Propose a new experiment."""
    exp = _engine.propose(
        hypothesis=payload.get("hypothesis", ""),
        origin=ExperimentOrigin(payload.get("origin", "manual")),
        changed_parameters=payload.get("changed_parameters", {}),
        notes=payload.get("notes", ""),
    )
    return {"experiment_id": exp.experiment_id, "status": exp.status.value}


@router.post("/grid-search")
def grid_search(payload: dict):
    """Create a grid search (proposes experiments, doesn't run)."""
    ids = _engine.grid_search(
        base_params=payload.get("base_params", {}),
        param_grid=payload.get("param_grid", {}),
        hypothesis_template=payload.get("hypothesis_template", ""),
    )
    return {"experiment_ids": ids, "count": len(ids)}


@router.get("/")
def list_experiments(status: str | None = None, origin: str | None = None, limit: int = 50):
    """List experiments, optionally filtered by status and/or origin."""
    all_exps = _engine.list_all()
    if status:
        try:
            from cudaquant.experiments.engine import ExperimentStatus
            st = ExperimentStatus(status)
            all_exps = [e for e in all_exps if e.status == st]
        except ValueError as err:
            raise HTTPException(400, f"Invalid status: {status}") from err
    if origin:
        all_exps = [e for e in all_exps if e.origin.value == origin]
    return [{"experiment_id": e.experiment_id, "hypothesis": e.hypothesis,
             "status": e.status.value, "origin": e.origin.value,
              "created_at": e.created_at, "metrics": e.metrics} for e in all_exps[:limit]]


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str):
    exp = _engine.get(experiment_id)
    if exp is None:
        raise HTTPException(404, "Experiment not found")
    return {"experiment_id": exp.experiment_id, "hypothesis": exp.hypothesis,
            "origin": exp.origin.value, "status": exp.status.value,
            "changed_parameters": exp.changed_parameters,
            "metrics": exp.metrics, "created_at": exp.created_at,
            "notes": exp.notes}
