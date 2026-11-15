"""Smoke tests: the server imports and everything registers."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from houston_opendata.app import mcp
from houston_opendata.config import settings

EXPECTED_TOOLS = {
    "houston_search_datasets",
    "houston_get_dataset",
    "houston_describe_table",
    "houston_query_records",
    "houston_browse_catalog",
}


def test_server_has_name():
    assert mcp.name == "Houston Open Data"


def test_default_transport_is_stdio():
    """Guard against accidentally shipping with a non-stdio default."""
    assert settings.mcp_transport == "stdio"


def test_routes_register_without_error():
    from houston_opendata.routes import register_routes

    register_routes(FastMCP("test"))  # must not raise


@pytest.mark.asyncio
async def test_all_tools_are_discoverable_and_read_only():
    tools = await mcp.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS
    for tool in tools:
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False


@pytest.mark.asyncio
async def test_app_and_mcp_share_one_set_of_tool_descriptions():
    """The Streamlit agent and MCP clients must describe each tool the same way."""
    from houston_opendata import agent
    from houston_opendata.tool_docs import TOOL_DESCRIPTIONS

    for tool in agent.tools(use_arcgis=True):
        assert tool["description"] == TOOL_DESCRIPTIONS[tool["name"]]
    for tool in await mcp.list_tools():
        assert tool.description == TOOL_DESCRIPTIONS[tool.name]
    assert "summary" in TOOL_DESCRIPTIONS["houston_query_records"].lower()
