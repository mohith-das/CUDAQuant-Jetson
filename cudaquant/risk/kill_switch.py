"""File-based kill switch for cross-process safety.

The kill switch is a sentinel file on disk. Any process that can place orders
must check it before acting; if the file exists, all new orders are rejected.
File-based state survives process restarts and is shared across processes, so
one process engaging the switch stops every other process too.
"""

from __future__ import annotations

import contextlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Environment gates required for live trading (BOTH must be satisfied).
LIVE_MODE_ENV = "TRADING_MODE"
LIVE_MODE_VALUE = "live"
LIVE_ACK_ENV = "ENABLE_LIVE_TRADING"
LIVE_ACK_VALUE = "I_UNDERSTAND_LIVE_TRADING_RISK"


class KillSwitch:
    """File-based kill switch for cross-process safety."""

    def __init__(self, filepath: str = "./.kill_switch"):
        self.filepath = Path(filepath)

    def engage(self, reason: str = "manual") -> None:
        """Write kill switch file. Blocks all new orders."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "engaged": True,
            "reason": str(reason),
            "engaged_at": datetime.now(timezone.utc).isoformat(),
        }
        # Atomic write: readers never observe a partially written file.
        tmp = self.filepath.with_name(self.filepath.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        os.replace(tmp, self.filepath)

    def disengage(self) -> None:
        """Remove kill switch file."""
        with contextlib.suppress(FileNotFoundError):
            self.filepath.unlink()

    def is_engaged(self) -> bool:
        """Check if kill switch file exists. Read timestamp and reason."""
        return self.filepath.exists()

    def status(self) -> dict:
        """Return kill-switch state including timestamp and reason (if any)."""
        if not self.filepath.exists():
            return {"engaged": False, "reason": None, "engaged_at": None}
        try:
            payload = json.loads(self.filepath.read_text())
            return {
                "engaged": True,
                "reason": payload.get("reason", "unknown"),
                "engaged_at": payload.get("engaged_at"),
            }
        except (json.JSONDecodeError, OSError):
            # Fail closed: a present but unreadable file is still engaged.
            return {"engaged": True, "reason": "unreadable", "engaged_at": None}

    @staticmethod
    def is_live_mode_enabled() -> bool:
        """Check if live trading gates are satisfied.

        Requires BOTH ``TRADING_MODE=live`` AND
        ``ENABLE_LIVE_TRADING=I_UNDERSTAND_LIVE_TRADING_RISK`` in the
        environment. Any other combination returns False.
        """
        mode = os.environ.get(LIVE_MODE_ENV, "").strip().lower()
        ack = os.environ.get(LIVE_ACK_ENV, "").strip()
        return mode == LIVE_MODE_VALUE and ack == LIVE_ACK_VALUE
