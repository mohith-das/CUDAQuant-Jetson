# CUDAQuant MCP Server

Exposes CUDAQuant platform tools to Claude Desktop / Claude Code via the
Model Context Protocol (MCP).

## Setup

### Prerequisites
- Tailscale network access to the Jetson (the API is bound to its Tailscale IP)
- `API_AUTH_TOKEN` from the Jetson's `.env` file
- Python 3.10+ with the `mcp` package installed

### Install
```bash
pip install mcp
```

### Claude Desktop Configuration
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cudaquant": {
      "command": "python",
      "args": ["/path/to/CUDAQuant/mcp_server/cudaquant_mcp.py"],
      "env": {
        "API_AUTH_TOKEN": "your-token-here",
        "DUCKDB_PATH": "/path/to/data/cudaquant.duckdb",
        "PYTHONPATH": "/path/to/CUDAQuant"
      }
    }
  }
}
```

### Claude Code Configuration
Add to `.claude/mcp.json`:
```json
{
  "mcpServers": {
    "cudaquant": {
      "command": "python",
      "args": ["/path/to/CUDAQuant/mcp_server/cudaquant_mcp.py"],
      "env": {
        "API_AUTH_TOKEN": "your-token-here",
        "PYTHONPATH": "/path/to/CUDAQuant"
      }
    }
  }
}
```

## Tools Exposed

### READ tools (always available)
| Tool | Description |
|---|---|
| `list_strategies` | Available trading strategies with parameter schemas |
| `list_experiments` | Experiment history with status/origin filters |
| `get_experiment` | Experiment details by ID |
| `list_models` | Model registry with champion/challenger status |
| `get_model` | Model details including metrics |
| `get_model_live_performance` | Realized vs backtest performance |
| `run_backtest_result` | Run a backtest (read-only, doesn't persist) |
| `get_regime_state` | Current market regime classification |
| `get_scheduler_status` | Scheduled job status and history |
| `get_dispatch_stats` | GPU vs CPU feature computation counts |
| `get_account` | Account cash, portfolio value, buying power |
| `get_positions` | Current open positions |
| `get_order_history` | Recent order history |

### WRITE tools (gated behind same validation as API/UI)
| Tool | Description |
|---|---|
| `propose_experiment` | Propose a new experiment (manual origin) |
| `promote_model` | Promote candidate→challenger or challenger→champion |
| `retire_model` | Retire a model |
| `run_scheduler_job_now` | Trigger a scheduler job immediately |
| `submit_paper_order` | Submit a paper order through FULL gate chain |

### Explicitly EXCLUDED (not exposed to any LLM interface)
- TRADING_MODE / ENABLE_LIVE_TRADING / SCHEDULER_AUTO_EXECUTE changes
- Kill switch engage (available, requires `confirm: "STOP"`)
- Kill switch disengage (human-UI-only — cannot be triggered by MCP)

## Safety

All WRITE tools go through the EXACT SAME validation chain as the UI/API:
1. Config gate (TRADING_MODE + ENABLE_LIVE_TRADING)
2. RiskGovernor.pre_trade_check()
3. KillSwitch.is_engaged()

No tool can bypass, weaken, or skip these gates. The MCP server has no
special privileges — it's just another client of the same service layer.
