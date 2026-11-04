"""Tools submodule — one tool per file.

Each tool module exposes a `register(mcp)` function. To add a tool, create
`tools/<your_tool>.py`, import it below, and call its `register` function.
"""

from __future__ import annotations

from houston_opendata.tools import (
    describe_table,
    get_dataset,
    list_groups,
    list_organizations,
    query_records,
    search_datasets,
)


def register_tools(mcp) -> None:
    """Register all tools with the MCP server."""
    search_datasets.register(mcp)
    get_dataset.register(mcp)
    describe_table.register(mcp)
    query_records.register(mcp)
    list_organizations.register(mcp)
    list_groups.register(mcp)


__all__ = ["register_tools"]
