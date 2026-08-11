#!/usr/bin/env python3
"""CUDAQuant MCP Server — exposes platform tools via FastMCP."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import FastMCP

from cudaquant.platform_tools.registry import READ_TOOLS, WRITE_TOOLS

mcp = FastMCP("cudaquant-mcp")

for name, fn in READ_TOOLS.items():
    mcp.add_tool(fn, name=name, description=fn.__doc__ or f"READ: {name}")

for name, fn in WRITE_TOOLS.items():
    mcp.add_tool(fn, name=name, description=f"WRITE: {name}")


if __name__ == "__main__":
    mcp.run()
