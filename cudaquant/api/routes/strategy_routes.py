"""Strategy API routes — list strategies, get parameter schemas."""
import inspect

from fastapi import APIRouter, Depends

from cudaquant.api.auth import require_auth
from cudaquant.strategies.implementations import (
    IntradayMomentum,
    MeanReversion,
    PairsRelativeValue,
)

router = APIRouter(prefix="/api/strategies", tags=["strategies"], dependencies=[Depends(require_auth)])

STRATEGY_REGISTRY = {
    "intraday_momentum": IntradayMomentum,
    "mean_reversion": MeanReversion,
    "pairs_relative_value": PairsRelativeValue,
}


def _get_param_schema(cls):
    """Introspect strategy __init__ signature for parameter names and defaults."""
    sig = inspect.signature(cls.__init__)
    params = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        info = {"name": name}
        if param.default is not inspect.Parameter.empty:
            info["default"] = param.default
        annotation = param.annotation
        if annotation is not inspect.Parameter.empty:
            if hasattr(annotation, "__name__"):
                info["type"] = annotation.__name__
            else:
                info["type"] = str(annotation)
        params[name] = info
    return params


@router.get("/")
def list_strategies():
    """List available strategy classes with their parameter schemas."""
    result = {}
    for name, cls in STRATEGY_REGISTRY.items():
        result[name] = {
            "name": name,
            "description": cls.__doc__ or "",
            "parameters": _get_param_schema(cls),
        }
    return result


@router.get("/{strategy_name}")
def get_strategy(strategy_name: str):
    """Get details for a specific strategy."""
    cls = STRATEGY_REGISTRY.get(strategy_name)
    if cls is None:
        return {"error": f"Unknown strategy: {strategy_name}"}
    return {
        "name": strategy_name,
        "description": cls.__doc__ or "",
        "parameters": _get_param_schema(cls),
    }
