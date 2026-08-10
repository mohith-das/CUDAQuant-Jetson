"""Health and readiness endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter

from cudaquant.config.settings import settings

health_router = APIRouter(tags=["health"])
readiness_router = APIRouter(tags=["readiness"])

APP_VERSION = "0.1.0"


def _check_gpu() -> dict:
    """Runtime GPU state — may differ from config intent if library missing."""
    gpu_active = False
    ml_gpu_active = False
    try:
        from cudaquant.features.gpu.bindings import gpu_available
        gpu_active = gpu_available()
    except Exception:
        pass
    try:
        from cudaquant.ml.gpu_models import _gpu_ml_available
        ml_gpu_active = _gpu_ml_available()
    except Exception:
        pass
    return {"gpu_active": gpu_active, "ml_gpu_active": ml_gpu_active}


@health_router.get("/health")
def health() -> dict:
    """Liveness probe — the process is up and serving."""
    return {
        "status": "ok",
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@readiness_router.get("/readiness")
def readiness() -> dict:
    """Readiness probe — reflects real dependency/config state."""
    gpu = _check_gpu()
    return {
        "ready": True,
        "checks": {
            "config_loaded": True,
            "trading_mode": settings.TRADING_MODE,
            "live_trading_enabled": settings.live_trading_enabled,
            "cuda_enabled": settings.CUDA_ENABLED,
            "gpu_active": gpu["gpu_active"],
            "ml_gpu_active": gpu["ml_gpu_active"],
        },
    }
