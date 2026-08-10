"""FastAPI application, routers, middleware, health/readiness."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cudaquant.api.routes import health_router, readiness_router
from cudaquant.config.settings import settings

logger = logging.getLogger("cudaquant.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "CUDAQuant API starting (mode=%s, live_trading=%s)",
        settings.TRADING_MODE,
        settings.live_trading_enabled,
    )
    yield
    logger.info("CUDAQuant API shutdown complete")


app = FastAPI(
    title="CUDAQuant API",
    version="0.1.0",
    lifespan=lifespan,
)

# Local-dev CORS: allow all origins/methods/headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(readiness_router)
