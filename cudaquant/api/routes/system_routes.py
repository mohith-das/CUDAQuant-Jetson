"""System & regime API routes."""
import time

from fastapi import APIRouter, Depends, Query

from cudaquant.api.auth import require_auth
from cudaquant.config.settings import settings
from cudaquant.features.dispatch import get_stats
from cudaquant.regimes.detector import RegimeDetector
from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator
from datetime import datetime, timezone, timedelta

system_router = APIRouter(prefix="/api/system", tags=["system"], dependencies=[Depends(require_auth)])
regime_router = APIRouter(prefix="/api/regimes", tags=["regimes"], dependencies=[Depends(require_auth)])

_start_time = time.time()


@system_router.get("/")
def system_info():
    """System info: uptime, version, GPU state."""
    gpu = {}
    try:
        from cudaquant.features.gpu.bindings import gpu_available
        gpu["gpu_active"] = gpu_available()
    except Exception:
        gpu["gpu_active"] = False
    try:
        from cudaquant.ml.gpu_models import _gpu_ml_available
        gpu["ml_gpu_active"] = _gpu_ml_available()
    except Exception:
        gpu["ml_gpu_active"] = False

    return {
        "version": "0.1.0",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "trading_mode": settings.TRADING_MODE,
        "cuda_enabled": settings.CUDA_ENABLED,
        "gpu_active": gpu.get("gpu_active", False),
        "ml_gpu_active": gpu.get("ml_gpu_active", False),
    }


@system_router.get("/dispatch-stats")
def dispatch_stats():
    """GPU vs CPU dispatch counts."""
    stats = get_stats()
    return {
        "gpu_calls": stats["gpu_calls"],
        "cpu_calls": stats["cpu_calls"],
        "bypass_config": stats["gpu_bypass_config"],
        "bypass_no_lib": stats["gpu_bypass_no_lib"],
        "bypass_size": stats["gpu_bypass_size"],
    }


@regime_router.post("/detect")
def detect_regimes(payload: dict):
    """Run regime detection on synthetic data."""
    symbols = payload.get("symbols", ["AAPL"])
    days = payload.get("days", 30)
    freq = BarFrequency(payload.get("frequency", "5m"))

    gen = SyntheticDataGenerator(seed=42)
    end = datetime.now(timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    df = gen.generate_bars(symbols, start, end, freq)

    detector = RegimeDetector()
    regimes = detector.detect(df)
    dist = detector.regime_distribution(df)

    return {
        "regimes": [{"timestamp": str(idx), "regime": r.value}
                     for idx, r in regimes.items()][:100],
        "distribution": dist,
    }
