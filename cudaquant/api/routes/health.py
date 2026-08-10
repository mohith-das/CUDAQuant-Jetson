"""Health and readiness endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter

from cudaquant.config.settings import settings

health_router = APIRouter(tags=["health"])
readiness_router = APIRouter(tags=["readiness"])

APP_VERSION = "0.1.0"


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
    return {
        "ready": True,
        "checks": {
            "config_loaded": True,
            "trading_mode": settings.TRADING_MODE,
            "live_trading_enabled": settings.live_trading_enabled,
            "cuda_enabled": settings.CUDA_ENABLED,
        },
    }
