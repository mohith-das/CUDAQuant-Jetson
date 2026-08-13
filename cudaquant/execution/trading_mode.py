"""Runtime trading-mode switch with DuckDB persistence and multi-gate safety.

The mode toggle separates two concepts:

- ``desired`` — the user's preference, persisted to DuckDB so it survives
  restarts.
- ``effective`` — what is actually active. It can only be ``"live"`` when the
  environment gates (``TRADING_MODE=live`` AND
  ``ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISK``) hold, the file-based
  kill switch is disarmed, and a live broker connection can be established.

Switching paper→live requires, in order:
  1. environment gates satisfied (the .env acknowledgement — a UI action alone
     can never enable live trading);
  2. confirmation phrase ``"LIVE"``;
  3. kill switch disarmed;
  4. live broker connection verified.

Switching live→paper is always allowed, instantly, with no confirmation.

The service is a process-wide singleton (``get_shared_trading_mode``), mirroring
``get_shared_engine``/``get_shared_registry`` so state cannot diverge across
routes, scheduler callbacks, and platform tools.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from cudaquant.config.settings import settings
from cudaquant.risk.kill_switch import KillSwitch

logger = logging.getLogger(__name__)

VALID_MODES = ("paper", "live")
LIVE_CONFIRM = "LIVE"


@dataclass
class ModeState:
    """Current trading-mode state."""

    desired: str = "paper"  # persisted user preference
    effective: str = "paper"  # what is actually active
    reason: str = ""  # why effective != desired (empty when they match)


class TradingModeService:
    """Runtime trading-mode switch, persisted and safety-gated."""

    def __init__(
        self,
        db_path: str | None = None,
        kill_switch: KillSwitch | None = None,
    ):
        self._db_path = db_path
        self._kill_switch = kill_switch or KillSwitch(settings.KILL_SWITCH_FILE)
        self._order_service = None  # bound later by build_order_service()
        self._state = ModeState()
        if self._db_path:
            self._init_db()
        self.init_from_boot()

    # ── Environment gates ───────────────────────────────────────────────────

    @staticmethod
    def env_live_eligible() -> tuple[bool, str]:
        """Environment gates: BOTH ``TRADING_MODE=live`` AND
        ``ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISK`` in the process
        environment. Any other combination is ineligible.
        """
        if not KillSwitch.is_live_mode_enabled():
            return (
                False,
                "env gates not satisfied: set TRADING_MODE=live and "
                "ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISK in .env",
            )
        return True, ""

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def init_from_boot(self) -> ModeState:
        """Determine effective mode at boot from persisted preference + gates.

        If the persisted preference is ``live`` but the environment gates no
        longer hold (or the kill switch is engaged), fail safe to paper and
        record the reason — never boot live without every gate.
        """
        desired = self._load_desired()
        if desired == "live":
            ok, reason = self.env_live_eligible()
            if not ok:
                self._state = ModeState(desired=desired, effective="paper", reason=reason)
                self._alert(
                    f"Booted in PAPER mode though live was requested: {reason} "
                    "(switch via UI once gates are satisfied)"
                )
            elif self._kill_switch.is_engaged():
                self._state = ModeState(
                    desired=desired, effective="paper",
                    reason="kill switch is engaged",
                )
                self._alert(
                    "Booted in PAPER mode though live was requested: kill switch engaged"
                )
            else:
                self._state = ModeState(desired=desired, effective="live")
        else:
            self._state = ModeState(desired=desired, effective="paper")
        logger.info(
            "Trading mode at boot: desired=%s effective=%s reason=%r",
            self._state.desired, self._state.effective, self._state.reason,
        )
        return self._state

    # ── Switching ───────────────────────────────────────────────────────────

    def switch(self, mode: str, confirm: str = "") -> tuple[bool, str]:
        """Switch trading mode. Returns ``(ok, message)``.

        paper→live is gated (env ack + confirmation phrase + kill switch +
        live broker connection). live→paper is always allowed. Switching to
        the already-active mode is an idempotent no-op.
        """
        if mode not in VALID_MODES:
            return False, f"invalid mode: {mode} (expected paper or live)"

        if self._state.effective == mode and self._state.desired == mode:
            return True, f"already in {mode} mode"

        if mode == "live":
            ok, reason = self.env_live_eligible()
            if not ok:
                return False, reason
            if confirm != LIVE_CONFIRM:
                return False, f"type '{LIVE_CONFIRM}' to confirm switching to live"
            if self._kill_switch.is_engaged():
                return False, "kill switch is engaged — disengage before switching to live"
            if self._order_service is not None:
                ok, reason = self._order_service.verify_live_connection()
                if not ok:
                    return False, reason

        # Apply: update the order service (governor + broker), persist, alert.
        if self._order_service is not None:
            self._order_service.set_mode(mode, paper=(mode == "paper"))
        self._state = ModeState(desired=mode, effective=mode)
        self._persist()
        self._alert(
            f"Trading mode switched to {mode.upper()} "
            f"(via UI, kill_switch={'engaged' if self._kill_switch.is_engaged() else 'disarmed'})"
        )
        logger.warning("Trading mode switched: desired=%s effective=%s", mode, mode)
        return True, f"switched to {mode} mode"

    # ── Wiring ──────────────────────────────────────────────────────────────

    def bind_order_service(self, order_service) -> None:
        """Bind the shared OrderService so switches rebuild broker + governor."""
        self._order_service = order_service

    # ── Accessors ───────────────────────────────────────────────────────────

    @property
    def effective_mode(self) -> str:
        return self._state.effective

    @property
    def state(self) -> ModeState:
        return self._state

    def get_state(self) -> dict:
        """Public state for API/UI."""
        return {
            "desired_mode": self._state.desired,
            "effective_mode": self._state.effective,
            "mode_reason": self._state.reason or None,
            "env_live_eligible": self.env_live_eligible()[0],
            "kill_switch_engaged": self._kill_switch.is_engaged(),
        }

    # ── Persistence (DuckDB) ────────────────────────────────────────────────

    def _init_db(self) -> None:
        import duckdb

        try:
            con = duckdb.connect(str(self._db_path))
            con.execute(
                "CREATE TABLE IF NOT EXISTS trading_mode_state ("
                "key VARCHAR PRIMARY KEY, value JSON)"
            )
            con.close()
        except ImportError:  # pragma: no cover - duckdb is a project dependency
            logger.info("duckdb not available — trading mode persistence disabled")
        except Exception as e:
            logger.error("Trading mode DB init failed: %s", e, exc_info=True)
            raise

    def _persist(self) -> None:
        if not self._db_path:
            return
        import duckdb

        try:
            con = duckdb.connect(str(self._db_path))
            con.execute(
                "INSERT OR REPLACE INTO trading_mode_state VALUES ('desired', ?)",
                [json.dumps({"mode": self._state.desired})],
            )
            con.close()
        except Exception as e:
            logger.error("Trading mode persist failed: %s", e, exc_info=True)
            raise

    def _load_desired(self) -> str:
        """Persisted preference; falls back to env TRADING_MODE.

        Fail-safe: any unreadable or malformed persisted row logs an error and
        falls back — a corrupted preference must never block boot or crash the
        service, and the safe fallback is the env value (paper by default).
        """
        if not self._db_path:
            return settings.TRADING_MODE
        import duckdb

        try:
            con = duckdb.connect(str(self._db_path))
            row = con.execute(
                "SELECT value FROM trading_mode_state WHERE key='desired'"
            ).fetchone()
            con.close()
            if row:
                data = json.loads(row[0])
                mode = data.get("mode") if isinstance(data, dict) else None
                if mode in VALID_MODES:
                    return mode
                logger.error(
                    "Trading mode persisted row malformed (%r) — falling back to env", data
                )
        except Exception as e:
            logger.error("Trading mode load failed: %s", e, exc_info=True)
            raise
        return settings.TRADING_MODE

    # ── Alerting ────────────────────────────────────────────────────────────

    @staticmethod
    def _alert(message: str) -> None:
        try:
            from cudaquant.alerts.telegram import TelegramAlerter

            TelegramAlerter().send(f"[CUDAQuant] {message}")
        except Exception as e:  # pragma: no cover - alerting must never break mode logic
            logger.warning("Trading mode alert failed: %s", e)


# ── Shared singleton ─────────────────────────────────────────────────────────
# Same pattern as ExperimentEngine.get_shared_engine() / ModelRegistry.get_shared_registry():
# one instance per process so persisted state and the bound OrderService can
# never diverge across routes, scheduler callbacks, and platform tools.

_shared: TradingModeService | None = None


def get_shared_trading_mode(db_path: str | None = None) -> TradingModeService:
    """Return the shared TradingModeService singleton."""
    global _shared
    if _shared is None:
        _shared = TradingModeService(db_path=db_path)
    return _shared


def effective_trading_mode() -> str:
    """Convenience accessor for consumers that only need the active mode."""
    return get_shared_trading_mode().effective_mode
