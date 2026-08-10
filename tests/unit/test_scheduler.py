"""Scheduler service safety tests.

Covers the 4th execution gate (SCHEDULER_AUTO_EXECUTE), the job config API,
and the guarantee that the scheduler can never auto-promote challengers.
"""

from cudaquant.scheduler.service import SchedulerService


def _service():
    """Fresh service with no persistence — deterministic in-memory state."""
    return SchedulerService(db_path=None)


class TestAutoExecuteGate:
    """The scheduler's auto-execution flag is the 4th independent gate."""

    def test_auto_execute_defaults_false(self):
        """SCHEDULER_AUTO_EXECUTE is False by default — the 4th gate blocks."""
        svc = _service()
        ok, reason = svc.can_auto_execute()
        assert ok is False
        assert "disabled" in reason.lower()

    def test_auto_execute_can_be_enabled(self):
        """Explicitly enabling the flag opens the 4th gate."""
        svc = _service()
        assert svc.set_auto_execute(True) is True
        ok, reason = svc.can_auto_execute()
        assert ok is True
        assert reason == "ok"

    def test_auto_execute_disabled_blocks(self):
        """Toggling the flag back off re-engages the block."""
        svc = _service()
        svc.set_auto_execute(True)
        assert svc.set_auto_execute(False) is False
        ok, _ = svc.can_auto_execute()
        assert ok is False


class TestNoAutoPromotion:
    """Promotion must be impossible through the scheduler under any config."""

    def test_auto_promotion_impossible(self):
        """The scheduler has NO promote_to_champion or auto_promote method."""
        svc = _service()
        assert not hasattr(svc, "promote_to_champion")
        assert not hasattr(svc, "auto_promote")
        assert not hasattr(svc, "promote_challenger")
        assert not hasattr(svc, "promote")


class TestJobConfig:
    """Runtime job configuration via the REST-facing API."""

    def test_jobs_are_toggleable(self):
        """update_job can disable a job; the returned dict reflects it."""
        svc = _service()
        result = svc.update_job("ingest", enabled=False)
        assert result["enabled"] is False

    def test_run_now_triggers_callback(self):
        """set_callback + run_now invokes the registered callback."""
        svc = _service()
        called = []

        def my_callback():
            called.append("ran")
            return "done"

        svc.set_callback("ingest", my_callback)
        result = svc.run_now("ingest")
        assert len(called) == 1
        assert result["last_result"] == "done"

    def test_unknown_job_rejected(self):
        """update_job on an unknown name returns an error dict."""
        svc = _service()
        result = svc.update_job("bogus")
        assert "error" in result
        assert "bogus" in result["error"]

    def test_get_state_returns_all_jobs(self):
        """get_state exposes all four scheduled jobs plus the auto-exec flag."""
        svc = _service()
        state = svc.get_state()
        assert set(state.keys()) >= {"ingest", "retrain", "evaluate", "llm_analyze"}
        assert "auto_execute_enabled" in state
        for name in ("ingest", "retrain", "evaluate", "llm_analyze"):
            assert state[name]["name"] == name
