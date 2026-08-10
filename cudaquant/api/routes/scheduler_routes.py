"""Scheduler API routes — configure, toggle, monitor scheduled jobs."""
from fastapi import APIRouter, Depends, HTTPException

from cudaquant.api.auth import require_auth

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"], dependencies=[Depends(require_auth)])

# The scheduler singleton is set by app.py on startup
_scheduler = None


def set_scheduler(svc):
    global _scheduler
    _scheduler = svc


def _get_scheduler():
    if _scheduler is None:
        raise HTTPException(503, "Scheduler not initialized")
    return _scheduler


@router.get("/")
def get_state():
    svc = _get_scheduler()
    return svc.get_state()


@router.put("/jobs/{job_name}")
def update_job(job_name: str, payload: dict):
    svc = _get_scheduler()
    enabled = payload.get("enabled")
    interval = payload.get("interval_seconds")
    if enabled is None and interval is None:
        raise HTTPException(400, "Must provide 'enabled' or 'interval_seconds'")
    return svc.update_job(job_name, enabled=enabled, interval_seconds=interval)


@router.post("/jobs/{job_name}/run-now")
def run_job_now(job_name: str):
    svc = _get_scheduler()
    return svc.run_now(job_name)


@router.put("/auto-execute")
def set_auto_execute(payload: dict):
    """Enable/disable auto-execution. Requires explicit confirmation."""
    confirm = payload.get("confirm", "")
    if confirm != "ENABLE":
        raise HTTPException(400, "Must include {'confirm': 'ENABLE'} to enable auto-execution")
    svc = _get_scheduler()
    enabled = svc.set_auto_execute(True)
    return {"auto_execute_enabled": enabled}


@router.delete("/auto-execute")
def disable_auto_execute():
    svc = _get_scheduler()
    svc.set_auto_execute(False)
    return {"auto_execute_enabled": False}
