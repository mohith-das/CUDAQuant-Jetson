"""MCP server integration tests — real client connection."""
import json

import pytest


@pytest.mark.asyncio
async def test_mcp_server_starts_and_lists_tools():
    from mcp import StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command="python", args=["mcp_server/cudaquant_mcp.py"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.list_tools()
        assert len(result.tools) > 0
        names = {t.name for t in result.tools}
        assert "list_models" in names
        assert "submit_paper_order" in names


@pytest.mark.asyncio
async def test_mcp_read_tool_works():
    from mcp import StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command="python", args=["mcp_server/cudaquant_mcp.py"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("list_models", {})
        # FastMCP uses structuredContent, not content
        sc = getattr(result, "structuredContent", None)
        if sc and "result" in sc:
            data = sc["result"]
        elif result.content:
            data = json.loads(result.content[0].text)
        else:
            data = []
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_mcp_write_tool_works():
    from mcp import StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command="python", args=["mcp_server/cudaquant_mcp.py"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("propose_experiment", {"hypothesis": "mcp_test"})
        sc = getattr(result, "structuredContent", None)
        if sc and "result" in sc:
            data = sc["result"]
        elif result.content:
            data = json.loads(result.content[0].text)
        else:
            data = {}
        assert "experiment_id" in data
