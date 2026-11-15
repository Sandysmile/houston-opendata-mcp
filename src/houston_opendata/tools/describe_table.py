"""Tool: show a table's columns and how its values are written."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import portal
from houston_opendata.models import ResourceId
from houston_opendata.tool_docs import TOOL_DESCRIPTIONS


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_describe_table",
        description=TOOL_DESCRIPTIONS["houston_describe_table"],
        annotations={
            "title": "Describe a Houston table",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_describe_table(resource_id: ResourceId) -> dict[str, Any]:
        try:
            return await portal.describe_table(resource_id)
        except portal.PortalError as exc:
            return exc.as_dict()
