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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP

from cudaquant.platform_tools.registry import READ_TOOLS, WRITE_TOOLS

mcp = FastMCP(
    "cudaquant-mcp",
)

# Register READ tools
for _name, _fn in READ_TOOLS.items():
    mcp.tool(name=_name, description=_fn.__doc__ or f"Read tool: {_name}")(_fn)

# Register WRITE tools
for _name, _fn in WRITE_TOOLS.items():
    mcp.tool(name=_name, description=f"WRITE: {_fn.__doc__ or _name}")(_fn)


if __name__ == "__main__":
    mcp.run()
