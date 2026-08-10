#!/usr/bin/env bash
# deploy_jetson.sh — Deploy CUDAQuant to Jetson Orin Nano
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Config ─────────────────────────────────────────────────────────────────────
JETSON_HOST="${JETSON_HOST:-matt.local}"
JETSON_USER="${JETSON_USER:-matt}"
JETSON_PATH="${JETSON_PATH:-~/cudaquant}"

echo "=== Deploying CUDAQuant-Jetson to ${JETSON_USER}@${JETSON_HOST}:${JETSON_PATH} ==="
echo ""

# ── Sync code ──────────────────────────────────────────────────────────────────
echo "Syncing code..."
rsync -avz --delete \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '.ruff_cache' \
    --exclude '.mypy_cache' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude 'data/' \
    --exclude '.opencode/cache' \
    --exclude '.opencode/logs' \
    --exclude '.venv/' \
    ./ "${JETSON_USER}@${JETSON_HOST}:${JETSON_PATH}/"

# ── Setup on Jetson ────────────────────────────────────────────────────────────
echo ""
echo "Running setup on Jetson..."
ssh "${JETSON_USER}@${JETSON_HOST}" "cd ${JETSON_PATH} && bash setup.sh"

# ── Build CUDA ─────────────────────────────────────────────────────────────────
echo ""
echo "Building CUDA kernels..."
ssh "${JETSON_USER}@${JETSON_HOST}" "cd ${JETSON_PATH}/cuda && bash build.sh"

# ── Run tests ──────────────────────────────────────────────────────────────────
echo ""
echo "Running tests..."
ssh "${JETSON_USER}@${JETSON_HOST}" "cd ${JETSON_PATH} && .venv/bin/python -m pytest tests/unit/ -q --tb=short"

# ── Restart service ────────────────────────────────────────────────────────────
echo ""
echo "Restarting service..."
ssh "${JETSON_USER}@${JETSON_HOST}" "cd ${JETSON_PATH} && bash stop.sh; bash start.sh &" &

sleep 3

# ── Health check ───────────────────────────────────────────────────────────────
echo ""
echo "Health check..."
HEALTH=$(ssh "${JETSON_USER}@${JETSON_HOST}" "curl -s http://127.0.0.1:8000/health" 2>/dev/null || echo "FAILED")
echo "Health: $HEALTH"

echo ""
echo "=== Deployment complete ==="
echo "Dashboard: http://${JETSON_HOST}:8000/"
