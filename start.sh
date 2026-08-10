#!/usr/bin/env bash
# start.sh — Start CUDAQuant-Jetson server
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── GPU library path ─────────────────────────────────────────────────────────
# Required for CUDA kernels, torch, and any RAPIDS libs to resolve.
export LD_LIBRARY_PATH="${SCRIPT_DIR}/cuda/lib:/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}"

# ── Activate venv ──────────────────────────────────────────────────────────────
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# ── Validate ───────────────────────────────────────────────────────────────────
echo "=== CUDAQuant-Jetson Starting ==="

python -c "
from cudaquant.config.settings import settings
live = settings.live_trading_enabled
print(f'Trading mode: {settings.TRADING_MODE}')
if live:
    print('⚠️  LIVE TRADING IS ENABLED')
else:
    print('✓ Paper/synthetic mode (live trading OFF)')
" || { echo "ERROR: Config validation failed"; exit 1; }

# ── Create data dir if needed ──────────────────────────────────────────────────
mkdir -p data

# ── Start server ───────────────────────────────────────────────────────────────
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo ""
echo "Starting server on http://${HOST}:${PORT}"
echo "Dashboard: http://${HOST}:${PORT}/"
echo "Health:    http://${HOST}:${PORT}/health"
echo ""

python -m uvicorn cudaquant.api.app:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level info
