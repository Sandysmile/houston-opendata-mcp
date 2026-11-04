"""Tool: list a queryable resource's columns."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from houston_opendata import portal


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
    async def houston_describe_table(
        resource_id: Annotated[str, "Resource `id` (UUID) from houston_get_dataset."],
    ) -> dict[str, Any]:
        """List a queryable resource's columns, types, and total row count.

        Call this before houston_query_records so that filters, column lists, and
        sorting use real column names. Only works when `queryable` is true.
        """
        try:
            return await portal.describe_table(resource_id)
        except portal.PortalError as exc:
            return exc.as_dict()
