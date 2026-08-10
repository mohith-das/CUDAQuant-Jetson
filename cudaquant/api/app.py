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
from cudaquant.api.routes.scheduler_routes import router as sched_router
from cudaquant.api.routes.scheduler_routes import set_scheduler
from cudaquant.api.routes.strategy_routes import router as strategy_router
from cudaquant.api.routes.system_routes import regime_router, system_router
from cudaquant.api.routes.ws_routes import ws_router
from cudaquant.config.settings import settings
from cudaquant.scheduler.service import SchedulerService

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
    # Start scheduler
    scheduler = SchedulerService(db_path=settings.DUCKDB_PATH)
    _setup_scheduler_callbacks(scheduler)
    set_scheduler(scheduler)
    scheduler.start()
    logger.info("Scheduler started")
    yield
    scheduler.stop()
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
app.include_router(sched_router)

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


def _setup_scheduler_callbacks(scheduler):
    """Wire scheduler jobs to real operations."""
    from datetime import datetime, timedelta, timezone

    from cudaquant.data.schemas import BarFrequency
    from cudaquant.data.synthetic import SyntheticDataGenerator
    from cudaquant.llm.agent import LLMResearchAgent
    from cudaquant.ml.models import TSLogisticRegression, prepare_targets
    from cudaquant.ml.registry import ModelRecord, ModelRegistry, ModelStatus

    registry = ModelRegistry(db_path=settings.DUCKDB_PATH)

    def ingest_callback():
        gen = SyntheticDataGenerator(seed=42)
        end = datetime.now(timezone.utc)
        start = end.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
        df = gen.generate_bars(["AAPL", "MSFT"], start, end, BarFrequency.MINUTE_5)
        return f"ingested {len(df)} bars for {df['symbol'].nunique()} symbols"

    def retrain_callback():
        gen = SyntheticDataGenerator(seed=42)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=60)
        df = gen.generate_bars(["AAPL"], start, end, BarFrequency.MINUTE_5)

        import numpy as np
        prices = df["close"].values.astype(np.float64)
        y = prepare_targets(df, horizon=5)
        valid = ~np.isnan(y)
        if valid.sum() < 50:
            return "not enough data to train"

        xmat = np.diff(prices) / prices[:-1]
        xmat = np.insert(xmat, 0, 0.0)
        xmat = xmat[:len(y)].reshape(-1, 1)
        xmat = np.nan_to_num(xmat, nan=0.0)

        model = TSLogisticRegression()
        model.fit(xmat[valid], y[valid])

        model_id = f"lr_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        record = ModelRecord(
            model_id=model_id,
            family="logistic_regression",
            status=ModelStatus.CANDIDATE,
            metrics={"n_samples": int(valid.sum())},
        )
        registry.register(record)
        return f"trained model {model_id} on {valid.sum()} samples"

    def evaluate_callback():
        champions = registry.list_by_status(ModelStatus.CHAMPION)
        challengers = registry.list_by_status(ModelStatus.CHALLENGER)
        return f"champions={len(champions)}, challengers={len(challengers)}"

    def llm_analyze_callback():
        agent = LLMResearchAgent()
        proposal = agent.propose_experiment({"champion": "none"})
        from cudaquant.experiments.engine import ExperimentOrigin, get_shared_engine
        engine = get_shared_engine(settings.DUCKDB_PATH)
        exp = engine.propose(
            hypothesis=proposal.hypothesis,
            origin=ExperimentOrigin.LLM,
            notes=proposal.reasoning_summary,
        )
        return f"LLM proposed experiment {exp.experiment_id}: {proposal.hypothesis[:80]}"

    scheduler.set_callback("ingest", ingest_callback)
    scheduler.set_callback("retrain", retrain_callback)
    scheduler.set_callback("evaluate", evaluate_callback)
    scheduler.set_callback("llm_analyze", llm_analyze_callback)
