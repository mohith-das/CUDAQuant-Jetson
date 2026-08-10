#!/usr/bin/env bash
# setup.sh — Install CUDAQuant-Jetson dependencies and prepare environment
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== CUDAQuant-Jetson Setup ==="
echo ""

# ── Detect environment ────────────────────────────────────────────────────────
ARCH=$(uname -m)
OS=$(uname -s)
IS_JETSON=false

if [ "$ARCH" = "aarch64" ] && [ -f /etc/nv_tegra_release ]; then
    IS_JETSON=true
    echo "✓ Detected Jetson (aarch64 + Tegra)"
elif [ "$OS" = "Darwin" ]; then
    echo "✓ Detected macOS development machine"
elif [ "$ARCH" = "x86_64" ]; then
    echo "✓ Detected x86_64 Linux"
else
    echo "⚠ Unknown platform: $OS / $ARCH"
fi

# ── Python venv ────────────────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "Activating venv..."
source .venv/bin/activate

# ── Install dependencies ───────────────────────────────────────────────────────
echo "Installing Python dependencies..."
pip install --upgrade pip --quiet

if [ "$IS_JETSON" = true ]; then
    pip install -e ".[dev,alpaca,gpu]" --quiet
else
    pip install -e ".[dev]" --quiet
fi

# ── CUDA build (Jetson only) ──────────────────────────────────────────────────
if [ "$IS_JETSON" = true ] && [ -d "/usr/local/cuda" ]; then
    echo ""
    echo "Building CUDA kernels..."
    bash cuda/build.sh
fi

# ── Create data directories ────────────────────────────────────────────────────
mkdir -p data

# ── Copy .env if not exists ────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit with your credentials."
fi

# ── Verify ──────────────────────────────────────────────────────────────────────
echo ""
echo "Running verification..."
python -c "
from cudaquant.config.settings import settings
print(f'  Trading mode: {settings.TRADING_MODE}')
print(f'  Live trading: {settings.live_trading_enabled}')
print(f'  CUDA enabled: {settings.CUDA_ENABLED}')
" 2>/dev/null || echo "  ⚠ Config check failed (may need .env setup)"

echo ""
echo "=== Setup complete ==="
echo "Run: ./start.sh"
