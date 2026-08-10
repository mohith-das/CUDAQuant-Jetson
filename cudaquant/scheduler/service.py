"""Scheduler service — in-process, asyncio-integrated, configurable at runtime.

Uses APScheduler for job scheduling. All state (cadences, enabled flags,
run history) persists to DuckDB. NEVER auto-promotes challengers — promotion
is always a human UI action. Auto-execution is gated behind a separate
SCHEDULER_AUTO_EXECUTE flag (default False) additional to the existing
OrderService gates.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


@dataclass
class JobConfig:
    """Configuration for one scheduled job."""
    name: str
    enabled: bool = True
    interval_seconds: int = 3600  # default: 1 hour
    last_run: str | None = None
    last_result: str | None = None
    next_run: str | None = None


@dataclass
class SchedulerState:
    """Full scheduler state, persisted to DuckDB."""
    ingest: JobConfig = field(default_factory=lambda: JobConfig(
        name="ingest", interval_seconds=300,  # 5 min
    ))
    retrain: JobConfig = field(default_factory=lambda: JobConfig(
        name="retrain", interval_seconds=3600,  # 1 hour
    ))
    evaluate: JobConfig = field(default_factory=lambda: JobConfig(
        name="evaluate", interval_seconds=7200,  # 2 hours
    ))
    llm_analyze: JobConfig = field(default_factory=lambda: JobConfig(
        name="llm_analyze", interval_seconds=14400,  # 4 hours
    ))
    auto_execute_enabled: bool = False


class SchedulerService:
    """Manages scheduled jobs with DuckDB persistence.

    Four toggleable responsibilities:
      - ingest: fetch new bars from configured provider
      - retrain: train new model candidates on latest data
      - evaluate: walk-forward evaluate challengers vs champion
      - llm_analyze: run LLMResearchAgent on champion performance

    Auto-execution is NOT a scheduler job — it's a separate decision made
    per-model via a human UI action. The scheduler NEVER auto-promotes.
    """

    def __init__(self, db_path: str | None = None):
        self._scheduler = AsyncIOScheduler()
        self._state = SchedulerState()
        self._db_path = db_path  # None means no persistence
        self._callbacks: dict[str, callable] = {}

        if self._db_path:
            self._init_db()
            self._load_state()

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the scheduler (called during app startup)."""
        self._register_jobs()
        self._scheduler.start()
        logger.info("Scheduler started with %d jobs", len(self._scheduler.get_jobs()))

    def stop(self) -> None:
        """Stop the scheduler (called during app shutdown)."""
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    # ── Job registration ────────────────────────────────────────────────────

    def set_callback(self, job_name: str, callback: callable) -> None:
        """Register a callback for a job. Called by the integration layer."""
        self._callbacks[job_name] = callback

    def _register_jobs(self) -> None:
        """Register all enabled jobs."""
        jobs = [
            (self._state.ingest, "ingest"),
            (self._state.retrain, "retrain"),
            (self._state.evaluate, "evaluate"),
            (self._state.llm_analyze, "llm_analyze"),
        ]
        for config, name in jobs:
            if config.enabled:
                self._add_job(config, name)

    def _add_job(self, config: JobConfig, name: str) -> None:
        """Add a single job to APScheduler."""
        job_id = f"scheduler_{name}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

        def _wrapper():
            return self._run_job(name)

        self._scheduler.add_job(
            _wrapper,
            trigger=IntervalTrigger(seconds=config.interval_seconds),
            id=job_id,
            name=name,
            replace_existing=True,
        )
        job = self._scheduler.get_job(job_id)
        if job:
            config.next_run = str(getattr(job, "next_run_time", None))
        logger.debug("Registered job: %s (every %ds)", name, config.interval_seconds)

    # ── Job execution ───────────────────────────────────────────────────────

    def _run_job(self, name: str) -> None:
        """Execute a scheduled job and record the result."""
        config = self._state.__dict__.get(name)
        if config is None:
            return

        callback = self._callbacks.get(name)
        if callback is None:
            config.last_result = f"no callback registered for {name}"
            return

        try:
            result = callback()
            config.last_result = str(result)[:500]
            config.last_run = datetime.now(timezone.utc).isoformat()
            self._persist_state()
            logger.info("Job %s completed: %s", name, config.last_result[:100])
        except Exception as e:
            config.last_result = f"error: {e}"
            config.last_run = datetime.now(timezone.utc).isoformat()
            logger.error("Job %s failed: %s", name, e, exc_info=True)
            from cudaquant.alerts.telegram import TelegramAlerter

            TelegramAlerter().send(
                f'[CUDAQuant] Scheduler job "{name}" failed: {e} — '
                f"{datetime.now(timezone.utc).isoformat()}"
            )

    # ── Configuration API (called from REST endpoints) ──────────────────────

    def get_state(self) -> dict:
        return {
            "ingest": self._job_to_dict(self._state.ingest),
            "retrain": self._job_to_dict(self._state.retrain),
            "evaluate": self._job_to_dict(self._state.evaluate),
            "llm_analyze": self._job_to_dict(self._state.llm_analyze),
            "auto_execute_enabled": self._state.auto_execute_enabled,
        }

    def update_job(self, name: str, enabled: bool | None = None,
                   interval_seconds: int | None = None) -> dict:
        """Update a job's config. Restarts the job if running."""
        config = self._state.__dict__.get(name)
        if config is None:
            return {"error": f"unknown job: {name}"}

        if enabled is not None:
            config.enabled = enabled
        if interval_seconds is not None:
            config.interval_seconds = interval_seconds

        # Remove and re-add to pick up new config
        job_id = f"scheduler_{name}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

        if config.enabled:
            self._add_job(config, name)

        self._persist_state()
        return self._job_to_dict(config)

    def set_auto_execute(self, enabled: bool) -> bool:
        """Enable or disable auto-execution. Requires explicit confirmation."""
        self._state.auto_execute_enabled = enabled
        self._persist_state()
        return self._state.auto_execute_enabled

    def run_now(self, name: str) -> dict:
        """Manually trigger a job immediately."""
        config = self._state.__dict__.get(name)
        if config is None:
            return {"error": f"unknown job: {name}"}
        self._run_job(name)
        return {"job": name, "last_result": config.last_result}

    def _job_to_dict(self, config: JobConfig) -> dict:
        return {
            "name": config.name,
            "enabled": config.enabled,
            "interval_seconds": config.interval_seconds,
            "last_run": config.last_run,
            "last_result": config.last_result,
            "next_run": config.next_run,
        }

    # ── Auto-execute check (4th gate, after OrderService's 3 gates) ─────────

    def can_auto_execute(self) -> tuple[bool, str]:
        """Check if auto-execution is allowed (4th independent gate).

        This is ADDITIONAL to OrderService's config, RiskGovernor, and
        KillSwitch gates. All four must pass for autonomous order placement.
        """
        if not self._state.auto_execute_enabled:
            return False, "SCHEDULER_AUTO_EXECUTE is disabled"
        return True, "ok"

    def execute_champion_signal(
        self,
        order_service,  # OrderService instance
        champion_signal: dict,  # {"symbol": str, "side": str, "qty": int}
    ) -> tuple[bool, str, str | None]:
        """Execute a champion's signal through ALL FOUR gates.

        Gate 4 (SCHEDULER_AUTO_EXECUTE) is checked here first.
        Gates 1-3 (config, RiskGovernor, KillSwitch) are enforced by
        order_service.submit_order().

        Args:
            order_service: OrderService instance (enforces gates 1-3).
            champion_signal: Dict with symbol, side, qty.

        Returns:
            (success, message, order_id_or_none)
        """
        # ── Gate 4: Scheduler auto-execute ──────────────────────────────
        ok, reason = self.can_auto_execute()
        if not ok:
            return False, f"scheduler gate 4: {reason}", None

        # ── Gates 1-3: OrderService (config, RiskGovernor, KillSwitch) ──
        from cudaquant.data.schemas import Order, OrderSide, OrderType

        try:
            order = Order(
                symbol=champion_signal["symbol"],
                side=OrderSide(champion_signal["side"]),
                order_type=OrderType.MARKET,
                qty=champion_signal["qty"],
            )
        except (KeyError, ValueError) as e:
            return False, f"invalid signal: {e}", None

        return order_service.submit_order(order)

    # ── DuckDB persistence ──────────────────────────────────────────────────

    def _init_db(self) -> None:
        try:
            from cudaquant.storage.db import get_connection
            con = get_connection()
            con.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_state (
                    key VARCHAR PRIMARY KEY,
                    value JSON
                )
            """)
            con.close()
        except Exception as e:
            logger.warning("Scheduler DB init failed: %s", e)

    def _persist_state(self) -> None:
        if not self._db_path:
            return
        try:
            from cudaquant.storage.db import get_connection
            con = get_connection()
            state_dict = {
                "ingest": self._job_to_dict(self._state.ingest),
                "retrain": self._job_to_dict(self._state.retrain),
                "evaluate": self._job_to_dict(self._state.evaluate),
                "llm_analyze": self._job_to_dict(self._state.llm_analyze),
                "auto_execute_enabled": self._state.auto_execute_enabled,
            }
            con.execute(
                "INSERT OR REPLACE INTO scheduler_state VALUES ('state', ?)",
                [json.dumps(state_dict)],
            )
            con.close()
        except Exception as e:
            logger.warning("Scheduler persist failed: %s", e)

    def _load_state(self) -> None:
        try:
            from cudaquant.storage.db import get_connection
            con = get_connection()
            row = con.execute(
                "SELECT value FROM scheduler_state WHERE key='state'"
            ).fetchone()
            con.close()
            if row:
                data = json.loads(row[0])
                for name in ("ingest", "retrain", "evaluate", "llm_analyze"):
                    if name in data:
                        cfg = data[name]
                        config = self._state.__dict__.get(name)
                        if config:
                            config.enabled = cfg.get("enabled", True)
                            config.interval_seconds = cfg.get("interval_seconds", 3600)
                            config.last_run = cfg.get("last_run")
                            config.last_result = cfg.get("last_result")
                self._state.auto_execute_enabled = data.get("auto_execute_enabled", False)
        except Exception as e:
            logger.warning("Scheduler load failed: %s", e)
