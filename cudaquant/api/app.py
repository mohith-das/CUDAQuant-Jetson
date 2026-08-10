"""FastAPI application — all routes, auth, CORS, LAN safety check."""
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cudaquant.api.routes.backtest_routes import router as backtest_router
from cudaquant.api.routes.data_routes import router as data_router
from cudaquant.api.routes.experiment_routes import router as experiment_router
from cudaquant.api.routes.health import health_router, readiness_router
from cudaquant.api.routes.model_routes import router as model_router
from cudaquant.api.routes.risk_routes import exec_router, risk_router
from cudaquant.api.routes.strategy_routes import router as strategy_router
from cudaquant.api.routes.system_routes import regime_router, system_router
from cudaquant.api.routes.ws_routes import ws_router
from cudaquant.config.settings import settings

logger = logging.getLogger("cudaquant.api")


def _check_lan_safety() -> None:
    """Fail closed if binding to LAN without auth token."""
    host = settings.HOST
    if host in ("127.0.0.1", "localhost", "::1"):
        return  # loopback is safe

    token = settings.API_AUTH_TOKEN
    if not token or token == "change-me-to-a-random-secret":
        logger.critical(
            "REFUSING TO START: HOST=%s (non-loopback) but API_AUTH_TOKEN is unset. "
            "Set API_AUTH_TOKEN in .env or bind to 127.0.0.1.",
            host,
        )
        sys.exit(1)

    logger.info("LAN bind enabled (HOST=%s), auth token configured", host)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_lan_safety()
    logger.info(
        "CUDAQuant API starting (mode=%s, live_trading=%s, host=%s)",
        settings.TRADING_MODE,
        settings.live_trading_enabled,
        settings.HOST,
    )
    yield
    logger.info("CUDAQuant API shutdown complete")


app = FastAPI(
    title="CUDAQuant API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow configured dev origin (e.g. Vite localhost:5173) or same-origin
dev_origin = os.environ.get("CORS_DEV_ORIGIN", "")
origins = [dev_origin] if dev_origin else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Public (no auth) ─────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(readiness_router)
app.include_router(ws_router)  # WebSocket — auth checked at connect

# ── API routes (auth required) ───────────────────────────────────────────────
app.include_router(data_router)
app.include_router(strategy_router)
app.include_router(backtest_router)
app.include_router(experiment_router)
app.include_router(model_router)
app.include_router(risk_router)
app.include_router(exec_router)
app.include_router(system_router)
app.include_router(regime_router)

# ── Static UI (mounted last so /api/* and /ws/* take precedence) ─────────────
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
    logger.info("Serving static UI from %s", frontend_dist)
else:
    @app.get("/")
    def root():
        return {"message": "CUDAQuant API running — frontend not built.",
                "docs": "/docs"}
