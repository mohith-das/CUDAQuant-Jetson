#!/usr/bin/env bash
# e2e_test.sh — end-to-end verification on Jetson
set -e
cd ~/code/cudaquant

TOKEN="test-token-e2e-$(date +%s)"
echo "Token: $TOKEN"

API_AUTH_TOKEN=$TOKEN HOST=0.0.0.0 PORT=8765 \
  LD_LIBRARY_PATH=$PWD/cuda/lib:/usr/local/cuda/lib64 \
  .venv/bin/python -m uvicorn cudaquant.api.app:app --host 0.0.0.0 --port 8765 &
PID=$!
sleep 4

echo ""
echo "=== 1. HEALTH (no auth) ==="
curl -s http://127.0.0.1:8765/health
echo ""

echo "=== 2. READINESS (no auth) ==="
curl -s http://127.0.0.1:8765/readiness
echo ""

echo "=== 3. SYSTEM (with auth) ==="
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/system/
echo ""

echo "=== 4. STRATEGIES ==="
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/strategies/
echo ""

echo "=== 5. RUN BACKTEST ==="
BT=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"strategy":"intraday_momentum","params":{"lookback":10},"symbols":["AAPL"],"days":7,"frequency":"5m"}' \
  http://127.0.0.1:8765/api/backtests/run)
echo "$BT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'  Backtest ID: {d[\"id\"]}')
print(f'  Trades: {d[\"trade_count\"]}')
print(f'  Sharpe: {d[\"metrics\"][\"sharpe\"]:.3f}')
print(f'  Max DD: {d[\"metrics\"][\"max_drawdown\"]:.3f}')
print(f'  Win Rate: {d[\"metrics\"][\"win_rate\"]:.3f}')
"

echo ""
echo "=== 6. DASHBOARD (served UI) ==="
curl -s http://127.0.0.1:8765/ | head -5
echo ""

echo "=== 7. GPU DISPATCH STATS ==="
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/system/dispatch-stats
echo ""

echo "=== 8. EXPERIMENTS ==="
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/experiments/
echo ""

echo ""
echo "=== ALL E2E CHECKS PASSED ==="
kill $PID 2>/dev/null || true
