"""Universe (watchlist) API routes — CRUD over the persistent UniverseStore.

The store lives in ``cudaquant.data.universe`` (worker-data) and is accessed
through the shared-singleton pattern used by ExperimentEngine/ModelRegistry.
Imported lazily so this module stays importable until that package lands;
handlers raise 503 with a clear message while it is missing.

Store interface (``cudaquant.data.universe``):
    get_shared_universe(db_path=None) -> store
    store.create(name, symbols)            -> Universe
    store.get(id)                          -> Universe | None
    store.list_all()                       -> list[Universe]
    store.update(id, name=None, symbols=None) -> Universe  (KeyError if missing)
    store.add_symbols(id, symbols)         -> Universe    (KeyError if missing)
    store.delete(id)                       -> None        (no-op if missing)
Universe records are dataclasses with ``id``, ``name``, ``symbols``,
``created_at``, ``updated_at`` (dicts are tolerated by the serializer).
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from cudaquant.api.auth import require_auth
from cudaquant.config.settings import settings

router = APIRouter(
    prefix="/api/universe",
    tags=["universe"],
    dependencies=[Depends(require_auth)],
)


def _get_store() -> Any:
    """Return the shared UniverseStore singleton or a clear 503."""
    try:
        from cudaquant.data.universe import get_shared_universe
    except ImportError as e:
        raise HTTPException(503, f"Universe service unavailable: {e}") from e
    return get_shared_universe(db_path=settings.DUCKDB_PATH)


def _get_universe_or_404(uid: str) -> Any:
    """Return a universe record or raise 404."""
    u = _get_store().get(uid)
    if u is None:
        raise HTTPException(404, "Universe not found")
    return u


def _validate_symbols(symbols: Any) -> list[str]:
    """Coerce to stripped uppercase symbols; 400 on non-list or empty entries."""
    if not isinstance(symbols, list):
        raise HTTPException(400, "symbols must be a list of non-empty strings")
    cleaned = [s.strip().upper() for s in symbols if isinstance(s, str)]
    if len(cleaned) != len(symbols) or any(s == "" for s in cleaned):
        raise HTTPException(400, "symbols must be a list of non-empty strings")
    return cleaned


def _serialize_universe(u: Any) -> dict:
    """Normalize a Universe record (dataclass or dict) to the API shape."""
    if isinstance(u, dict):
        uid = u.get("id") or u.get("uid")
        name = u.get("name", "")
        symbols = u.get("symbols") or []
        created_at = u.get("created_at", "")
        updated_at = u.get("updated_at", "")
    else:
        uid = getattr(u, "id", None) or getattr(u, "uid", None)
        name = getattr(u, "name", "")
        symbols = getattr(u, "symbols", []) or []
        created_at = getattr(u, "created_at", "")
        updated_at = getattr(u, "updated_at", "")
    return {
        "id": uid,
        "name": name,
        "symbols": sorted(set(symbols)),
        "created_at": created_at,
        "updated_at": updated_at,
    }


@router.get("/")
def list_universes():
    """List all universes."""
    return [_serialize_universe(u) for u in _get_store().list_all()]


@router.post("/", status_code=201)
def create_universe(payload: dict):
    """Create a universe with a name and optional symbols."""
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(400, "name is required")
    symbols = _validate_symbols(payload.get("symbols", []))
    return _serialize_universe(_get_store().create(name=name.strip(), symbols=symbols))


@router.get("/{uid}")
def get_universe(uid: str):
    """Return a single universe."""
    return _serialize_universe(_get_universe_or_404(uid))


@router.put("/{uid}")
def update_universe(uid: str, payload: dict):
    """Update a universe's name and/or symbols."""
    name = payload.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise HTTPException(400, "name must be a non-empty string")
    symbols = payload.get("symbols")
    if symbols is not None:
        symbols = _validate_symbols(symbols)
    _get_universe_or_404(uid)
    try:
        u = _get_store().update(uid, name=name.strip() if name else None, symbols=symbols)
    except KeyError as e:
        raise HTTPException(404, "Universe not found") from e
    return _serialize_universe(u)


@router.delete("/{uid}")
def delete_universe(uid: str):
    """Delete a universe."""
    _get_universe_or_404(uid)
    _get_store().delete(uid)
    return {"deleted": uid}


@router.post("/{uid}/symbols")
def add_symbols(uid: str, payload: dict):
    """Merge symbols into a universe (dedup sorted in the response)."""
    symbols = _validate_symbols(payload.get("symbols"))
    _get_universe_or_404(uid)
    try:
        u = _get_store().add_symbols(uid, symbols)
    except KeyError as e:
        raise HTTPException(404, "Universe not found") from e
    return _serialize_universe(u)
