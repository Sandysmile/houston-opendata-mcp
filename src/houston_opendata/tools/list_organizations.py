"""Tool: list publishing organizations (departments) and their dataset counts."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import portal


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_list_organizations",
        annotations={
            "title": "List Houston organizations",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_list_organizations() -> dict[str, Any]:
        """List publishing organizations (departments) and their dataset counts.

        Use an organization's `name` as the `organization` filter in
        houston_search_datasets.
        """
        try:
            return {"organizations": await portal.list_organizations()}
        except portal.PortalError as exc:
            return exc.as_dict()
