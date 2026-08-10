"""Model registry API routes."""
from fastapi import APIRouter, Depends, HTTPException

from cudaquant.api.auth import require_auth
from cudaquant.ml.registry import ModelRegistry, ModelStatus

router = APIRouter(prefix="/api/models", tags=["models"], dependencies=[Depends(require_auth)])

_registry = ModelRegistry()


@router.get("/")
def list_models(status: str | None = None):
    """List models, optionally filtered by status."""
    if status:
        try:
            st = ModelStatus(status)
            models = _registry.list_by_status(st)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    else:
        models = _registry.list_all()
    return [{"model_id": m.model_id, "family": m.family, "version": m.version,
             "status": m.status.value, "metrics": m.metrics,
             "created_at": m.created_at} for m in models]


@router.get("/{model_id}")
def get_model(model_id: str):
    m = _registry.get(model_id)
    if m is None:
        raise HTTPException(404, "Model not found")
    return {"model_id": m.model_id, "family": m.family, "version": m.version,
            "status": m.status.value, "metrics": m.metrics,
            "hyperparameters": m.hyperparameters, "created_at": m.created_at}


@router.post("/{model_id}/promote")
def promote_model(model_id: str):
    """Promote model: candidate→challenger or challenger→champion."""
    m = _registry.get(model_id)
    if m is None:
        raise HTTPException(404, "Model not found")
    if m.status == ModelStatus.CANDIDATE:
        ok = _registry.promote_to_challenger(model_id)
    elif m.status == ModelStatus.CHALLENGER:
        ok = _registry.promote_to_champion(model_id)
    else:
        raise HTTPException(400, f"Cannot promote from status: {m.status.value}")
    return {"success": ok, "model_id": model_id, "status": _registry.get(model_id).status.value}


@router.post("/{model_id}/retire")
def retire_model(model_id: str):
    ok = _registry.retire(model_id)
    return {"success": ok, "model_id": model_id}
