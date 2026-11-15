"""Tool: open one dataset — its metadata, resources, and their columns."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import portal
from houston_opendata.models import DatasetRef
from houston_opendata.tool_docs import TOOL_DESCRIPTIONS


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_get_dataset",
        description=TOOL_DESCRIPTIONS["houston_get_dataset"],
        annotations={
            "title": "Get a Houston dataset",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_get_dataset(dataset: DatasetRef) -> dict[str, Any]:
        try:
            return await portal.get_dataset(dataset)
        except portal.PortalError as exc:
            return exc.as_dict()
