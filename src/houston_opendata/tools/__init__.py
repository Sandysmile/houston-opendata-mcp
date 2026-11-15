"""Tools submodule — one tool per file.

Each tool module exposes a `register(mcp)` function. To add a tool, create
`tools/<your_tool>.py`, import it below, and call its `register` function.
"""

from __future__ import annotations

from houston_opendata.config import settings
from houston_opendata.tools import (
    air_quality,
    browse_catalog,
    describe_table,
    get_dataset,
    lookup_address,
    query_records,
    search_datasets,
    weather_forecast,
)


def register_tools(mcp) -> None:
    """Register all tools with the MCP server."""
    search_datasets.register(mcp)
    get_dataset.register(mcp)
    describe_table.register(mcp)
    query_records.register(mcp)
    browse_catalog.register(mcp)
    if settings.use_arcgis:  # Ask Houston+ only
        lookup_address.register(mcp)
        weather_forecast.register(mcp)
        air_quality.register(mcp)


__all__ = ["register_tools"]
