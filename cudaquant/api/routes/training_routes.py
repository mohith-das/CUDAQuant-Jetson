"""Training API routes — run and track model training jobs.

TrainingService lives in ``cudaquant.ml.training`` (worker-ml) and is imported
lazily so this module stays importable until that package lands; handlers
raise 503 with a clear message while it is missing.

Service interface (``cudaquant.ml.training``):
    get_shared_training_service(db_path) -> service
    service.run(symbols, model_family, features=None, horizon=5, universe_id=None) -> TrainingRun
    service.list_all(limit=50) -> list[TrainingRun]  (newest first)
    service.get(run_id)        -> TrainingRun | None
Validation errors raise ValueError (surfaced as 400); training failures are
recorded as ``status="failed"`` runs and returned (surfaced as 200). Runs are
dataclasses with ``id``, ``status``, ``model_id``, ``metrics``, ``error``,
``created_at`` (dicts are tolerated by the serializer).
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from cudaquant.api.auth import require_auth
from cudaquant.config.settings import settings

router = APIRouter(
    prefix="/api/training",
    tags=["training"],
    dependencies=[Depends(require_auth)],
)

MODEL_FAMILIES = ("logistic_regression", "random_forest")


def _get_service() -> Any:
    """Return the shared TrainingService singleton or a clear 503."""
    try:
        from cudaquant.ml.training import get_shared_training_service
    except ImportError as e:
        raise HTTPException(503, f"Training service unavailable: {e}") from e
    return get_shared_training_service(settings.DUCKDB_PATH)


def _resolve_symbols(payload: dict) -> tuple[list[str], str | None]:
    """Resolve training symbols from universe_id (preferred) or direct symbols.

    Returns (symbols, universe_id) so the run record keeps universe lineage.
    """
    universe_id = payload.get("universe_id")
    if universe_id:
        try:
            from cudaquant.data.universe import get_shared_universe
        except ImportError as e:
            raise HTTPException(503, f"Universe service unavailable: {e}") from e
        universe = get_shared_universe(db_path=settings.DUCKDB_PATH).get(universe_id)
        if universe is None:
            raise HTTPException(404, "Universe not found")
        resolved = (
            universe.get("symbols") or []
            if isinstance(universe, dict)
            else getattr(universe, "symbols", []) or []
        )
        if not resolved:
            raise HTTPException(400, "Universe has no symbols to train on")
    else:
        symbols = payload.get("symbols")
        if not isinstance(symbols, list) or not symbols:
            raise HTTPException(400, "symbols or universe_id is required")
        resolved = symbols
    cleaned = [s.strip().upper() for s in resolved if isinstance(s, str)]
    if not cleaned or any(s == "" for s in cleaned) or len(cleaned) != len(resolved):
        raise HTTPException(400, "symbols must be a non-empty list of non-empty strings")
    return sorted(set(cleaned)), universe_id


def _serialize_run(run: Any) -> dict:
    """Normalize a TrainingRun record (dataclass or dict) to the API shape."""
    if isinstance(run, dict):
        rid = run.get("id") or run.get("run_id")
        status = run.get("status", "")
        model_id = run.get("model_id")
        metrics = run.get("metrics") or {}
        error = run.get("error")
        created_at = run.get("created_at", "")
        extras = {
            key: run.get(key)
            for key in ("universe_id", "symbols", "model_family", "features", "horizon")
        }
    else:
        rid = getattr(run, "id", None) or getattr(run, "run_id", None)
        status = getattr(run, "status", "")
        model_id = getattr(run, "model_id", None)
        metrics = getattr(run, "metrics", {}) or {}
        error = getattr(run, "error", None)
        created_at = getattr(run, "created_at", "")
        extras = {
            key: getattr(run, key, None)
            for key in ("universe_id", "symbols", "model_family", "features", "horizon")
        }
    body = {
        "id": rid,
        "status": status,
        "model_id": model_id,
        "metrics": metrics,
        "error": error,
        "created_at": created_at,
    }
    body.update({k: v for k, v in extras.items() if v is not None})
    return body


@router.post("/run")
def run_training(payload: dict):
    """Run a training job synchronously from symbols or a universe."""
    model_family = payload.get("model_family")
    if model_family not in MODEL_FAMILIES:
        raise HTTPException(400, f"model_family must be one of {MODEL_FAMILIES}")
    features = payload.get("features")
    if features is not None and (
        not isinstance(features, list)
        or any(not isinstance(f, str) or not f.strip() for f in features)
    ):
        raise HTTPException(400, "features must be a list of non-empty strings")
    horizon = payload.get("horizon", 5)
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon <= 0:
        raise HTTPException(400, "horizon must be a positive integer")

    symbols, universe_id = _resolve_symbols(payload)
    try:
        run = _get_service().run(
            symbols=symbols,
            model_family=model_family,
            features=features,
            horizon=horizon,
            universe_id=universe_id,
        )
    except ValueError as e:  # service-side client errors (e.g. unsupported features)
        raise HTTPException(400, str(e)) from e
    body = _serialize_run(run)
    status_code = 201 if body.get("status") == "completed" else 200
    return JSONResponse(status_code=status_code, content=body)


@router.get("/")
def list_runs(limit: int = 50):
    """List training runs, newest first."""
    return [_serialize_run(r) for r in _get_service().list_all(limit=limit)]


@router.get("/{rid}")
def get_run(rid: str):
    """Return a single training run."""
    run = _get_service().get(rid)
    if run is None:
        raise HTTPException(404, "Training run not found")
    return _serialize_run(run)
