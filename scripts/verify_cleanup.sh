#!/usr/bin/env bash
# verify_cleanup.sh — Cancel all open Alpaca paper orders and kill stray uvicorn processes.
# Run at the start and end of every verification round.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=== CUDAQuant Cleanup ==="

# Kill stray uvicorn processes on known test ports
STRAY=$(ps aux | grep '[u]vicorn.*876[5-9]\|877[0-9]' | awk '{print $2}' || true)
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
