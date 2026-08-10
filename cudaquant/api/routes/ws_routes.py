"""WebSocket event stream — single endpoint broadcasting typed events."""
import asyncio
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from cudaquant.features.dispatch import get_stats

ws_router = APIRouter(tags=["websocket"])

# Active connections
_active: list[WebSocket] = []


async def _broadcast(event_type: str, data: dict) -> None:
    """Send a typed event to all connected clients."""
    dead = []
    for ws in _active:
        try:
            await ws.send_json({"type": event_type, "data": data, "ts": time.time()})
        except Exception:
            dead.append(ws)
    for ws in dead:
        _active.remove(ws)


def broadcast_event(event_type: str, data: dict) -> None:
    """Non-async entry point for broadcasting from sync code."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_broadcast(event_type, data))
    except RuntimeError:
        pass


@ws_router.websocket("/ws/events")
async def events_websocket(ws: WebSocket):
    """Single WebSocket endpoint for all event types.

    Events broadcast: experiment_progress, backtest_complete,
    order_filled, kill_switch_triggered, model_promoted,
    dispatch_stats_update.
    """
    await ws.accept()
    _active.append(ws)

    # Send initial state
    await ws.send_json({"type": "connected", "data": {"message": "WebSocket connected"}, "ts": time.time()})

    try:
        # Periodic dispatch stats push
        while True:
            await asyncio.sleep(10)
            stats = get_stats()
            await ws.send_json({"type": "dispatch_stats_update", "data": stats, "ts": time.time()})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if ws in _active:
            _active.remove(ws)
