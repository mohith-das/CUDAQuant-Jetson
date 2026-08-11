#!/usr/bin/env python3
"""CUDAQuant MCP Server — exposes platform tools via the Model Context Protocol.

Connects via stdio transport for Claude Desktop / Claude Code.
Requires: Tailscale network access to the Jetson + API_AUTH_TOKEN set in env.

Setup: pip install -e ".[mcp]", then configure Claude Desktop/Code per docs/MCP.md.

Uses mcp>=2.0's high-level MCPServer API (mcp.server.mcpserver) — NOT the
older @server.list_tools()/@server.call_tool() decorator pattern from
earlier SDK versions, which does not exist on this SDK's low-level Server
class and will raise AttributeError if used.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.mcpserver import MCPServer

from cudaquant.platform_tools.registry import READ_TOOLS, WRITE_TOOLS

server = MCPServer(
    name="cudaquant-mcp",
    description="CUDAQuant-Jetson platform tools — read-only market/model/experiment "
    "queries plus gated write actions (paper orders, promotions, kill switch engage). "
    "All writes go through the same OrderService/RiskGovernor/KillSwitch chain as the "
    "REST API. TRADING_MODE, ENABLE_LIVE_TRADING, SCHEDULER_AUTO_EXECUTE, and kill "
    "switch disengage are never exposed here — human-UI-only.",
)

for _name, _fn in READ_TOOLS.items():
    server.add_tool(_fn, name=_name, description=_fn.__doc__ or f"Read tool: {_name}")

for _name, _fn in WRITE_TOOLS.items():
    server.add_tool(_fn, name=_name, description=f"WRITE: {_fn.__doc__ or _name}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(server.run_stdio_async())
