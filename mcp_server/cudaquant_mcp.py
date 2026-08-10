#!/usr/bin/env python3
"""CUDAQuant MCP Server — exposes platform tools via the Model Context Protocol.

Connects via stdio transport for Claude Desktop / Claude Code.
Requires: Tailscale network access to the Jetson + API_AUTH_TOKEN set in env.

READ tools: always available.
WRITE tools: require explicit confirmation; go through same gate chain as API.
EXCLUDED: TRADING_MODE, ENABLE_LIVE_TRADING, SCHEDULER_AUTO_EXECUTE,
kill switch disengage (human-UI-only).
"""

import json
import os
import sys

# Ensure the cudaquant package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from cudaquant.platform_tools.registry import READ_TOOLS, WRITE_TOOLS

server = Server("cudaquant-mcp")

# ── Tool definitions ─────────────────────────────────────────────────────────


def _build_tools() -> list[Tool]:
    tools = []
    for name, fn in READ_TOOLS.items():
        tools.append(Tool(
            name=name,
            description=fn.__doc__ or f"Read tool: {name}",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": True},
        ))
    for name, fn in WRITE_TOOLS.items():
        tools.append(Tool(
            name=name,
            description=f"WRITE tool: {name}. {fn.__doc__ or ''}",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": True},
        ))
    return tools


@server.list_tools()
async def list_tools() -> list[Tool]:
    return _build_tools()


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Check READ tools first
    fn = READ_TOOLS.get(name)
    if fn:
        try:
            result = fn(**arguments)
            return [TextContent(type="text", text=json.dumps(result, default=str, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    # Check WRITE tools
    fn = WRITE_TOOLS.get(name)
    if fn:
        # Explicit exclusions
        if name in ("kill_switch_engage", "kill_switch_disengage"):
            return [TextContent(type="text", text=json.dumps({"error": "kill switch operations are human-UI-only"}, indent=2))]
        try:
            result = fn(**arguments)
            return [TextContent(type="text", text=json.dumps(result, default=str, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}, indent=2))]


# ── Main ─────────────────────────────────────────────────────────────────────


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
