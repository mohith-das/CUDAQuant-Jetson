"""MCP server integration tests — real client connection."""
import json

import pytest


@pytest.mark.asyncio
async def test_mcp_server_starts_and_lists_tools():
    """MCP server starts, real client connects, tools/list works."""
    from mcp import StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command="python",
        args=["mcp_server/cudaquant_mcp.py"],
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.list_tools()
        assert len(result.tools) > 0, "Should have at least 1 tool"
        # Verify key tools exist
        names = {t.name for t in result.tools}
        assert "list_models" in names, "READ tool missing"
        assert "list_strategies" in names, "READ tool missing"
        assert "submit_paper_order" in names, "WRITE tool missing"
        assert "propose_experiment" in names, "WRITE tool missing"


@pytest.mark.asyncio
async def test_mcp_read_tool_works():
    """Call a real READ tool through MCP client."""
    from mcp import StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command="python",
        args=["mcp_server/cudaquant_mcp.py"],
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("list_models", {})
        is_err = getattr(result, "isError", getattr(result, "is_error", False))
        assert not is_err, f"Tool call errored: {result}"
        # structuredContent (camelCase) is the reliable field on this SDK;
        # handle both snake/camel for compat across versions.
        sc = getattr(result, "structuredContent", getattr(result, "structured_content", None))
        data = sc.get("result", sc) if sc is not None else json.loads(result.content[0].text)
        assert isinstance(data, list), f"Expected list, got {type(data)}"


@pytest.mark.asyncio
async def test_mcp_write_tool_works():
    """Call a real WRITE tool through MCP client."""
    from mcp import StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command="python",
        args=["mcp_server/cudaquant_mcp.py"],
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(
            "propose_experiment",
            {"hypothesis": "mcp_write_test"},
        )
        text = result.content[0].text
        data = json.loads(text)
        assert "experiment_id" in data
