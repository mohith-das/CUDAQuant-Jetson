"""System & regime API routes."""
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from cudaquant.api.auth import require_auth
from cudaquant.config.settings import settings
from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator
from cudaquant.features.dispatch import get_stats
from cudaquant.regimes.detector import RegimeDetector

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

    from cudaquant.execution.trading_mode import get_shared_trading_mode
    tm = get_shared_trading_mode(settings.DUCKDB_PATH).get_state()

    return {
        "version": "0.1.0",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "trading_mode": tm["effective_mode"],
        "desired_mode": tm["desired_mode"],
        "mode_reason": tm["mode_reason"],
        "cuda_enabled": settings.CUDA_ENABLED,
        "gpu_active": gpu.get("gpu_active", False),
        "ml_gpu_active": gpu.get("ml_gpu_active", False),
        "mcp_installed": _check_mcp_installed(),
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
    }


def _check_mcp_installed() -> bool:
    """Check if mcp package is actually installed."""
    try:
        import mcp  # noqa: F401
        return True
    except ImportError:
        return False


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
        "regimes": [{"timestamp": str(idx), "regime": getattr(r, "value", str(r))}
                     for idx, r in regimes.items()][:100],
        "distribution": dist,
    }
