"""Tool: show a table's columns and how its values are written."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import portal
from houston_opendata.models import ResourceId


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_describe_table",
        annotations={
            "title": "Describe a Houston table",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_describe_table(resource_id: ResourceId) -> dict[str, Any]:
        """Show a table's columns, types, row count, and three sample rows.

        Use before filtering when you need to see how values are written, since
        filters match exactly (is it "HITS" or "Houston IT"? "K" or "District
        K"?). houston_get_dataset already lists columns for the newest tables, so
        call this mainly for older tables or to check value formats.
        """
        try:
            return await portal.describe_table(resource_id)
        except portal.PortalError as exc:
            return exc.as_dict()
