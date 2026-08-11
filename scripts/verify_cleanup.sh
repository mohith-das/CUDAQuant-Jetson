#!/usr/bin/env bash
# verify_cleanup.sh — Cancel all open Alpaca paper orders and kill stray uvicorn processes.
# Run at the start and end of every verification round.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=== CUDAQuant Cleanup ==="

# Kill stray uvicorn processes — but skip the real production server
# if it's bound to the configured HOST:PORT in .env or env vars.
REAL_PORT="${PORT:-8000}"
STRAY=""
for pid in $(ps aux | grep '[u]vicorn.*cudaquant' | awk '{print $2}'); do
    # Check if this process is listening on the real port
    LISTENING=$(ss -tlnp 2>/dev/null | grep ":$REAL_PORT " | grep "$pid" || true)
    if [ -n "$LISTENING" ]; then
        echo "Skipping production server PID=$pid (listening on port $REAL_PORT)"
    else
        STRAY="$STRAY $pid"
    fi
done
STRAY=$(echo "$STRAY" | xargs)
if [ -n "$STRAY" ]; then
    echo "Killing stray uvicorn: $STRAY"
    kill $STRAY 2>/dev/null || true
    sleep 1
else
    echo "No stray uvicorn processes"
fi

# Cancel all open Alpaca paper orders
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

echo "Cancelling open Alpaca orders..."
$PYTHON -c "
from cudaquant.providers.alpaca_broker import AlpacaBroker
b = AlpacaBroker()
if b.is_connected:
    count = b.cancel_all_orders()
    print(f'  Cancelled {count} open orders')
else:
    print('  Alpaca not configured — skipping')
" 2>/dev/null || echo "  (order cleanup skipped — no credentials or error)"

echo "=== Cleanup complete ==="
