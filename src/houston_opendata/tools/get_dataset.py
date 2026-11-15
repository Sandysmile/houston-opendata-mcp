"""Tool: open one dataset — its metadata, resources, and their columns."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import portal
from houston_opendata.models import DatasetRef


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_get_dataset",
        annotations={
            "title": "Get a Houston dataset",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_get_dataset(dataset: DatasetRef) -> dict[str, Any]:
        """Open a dataset: who publishes it, how current it is, its resources, and
        the columns and row count of each queryable resource.

        Answers "what's in this dataset and which table should I query?" in one
        call. `newest_queryable_resource` picks the latest table (for example
        Payroll 2026 out of yearly tables), so "most recent" questions need no
        guessing. Resources with queryable=true go straight to
        houston_query_records; others are reachable through `download_url`.
        """
        try:
            return await portal.get_dataset(dataset)
        except portal.PortalError as exc:
            return exc.as_dict()
