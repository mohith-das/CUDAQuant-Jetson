#!/usr/bin/env bash
# stop.sh — Gracefully stop CUDAQuant-Jetson
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE=".cudaquant.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping CUDAQuant (PID $PID)..."
        kill -TERM "$PID"
        sleep 2
        if kill -0 "$PID" 2>/dev/null; then
            echo "Force stopping..."
            kill -KILL "$PID"
        fi
        echo "Stopped."
    else
        echo "PID $PID not running — removing stale PID file."
    fi
    rm -f "$PID_FILE"
else
    # Fallback: find by process name
    PIDS=$(pgrep -f "uvicorn cudaquant" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "Stopping uvicorn processes: $PIDS"
        kill -TERM $PIDS 2>/dev/null || true
        sleep 2
        kill -KILL $PIDS 2>/dev/null || true
        echo "Stopped."
    else
        echo "No running CUDAQuant process found."
    fi
fi

echo "Done."
