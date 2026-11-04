"""Tool: list the portal's topic groups and their dataset counts."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import portal


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_list_groups",
        annotations={
            "title": "List Houston topic groups",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_list_groups() -> dict[str, Any]:
        """List the portal's topic groups and their dataset counts.

        Use a group's `name` as the `group` filter in
        houston_search_datasets.
        """
        try:
            return {"groups": await portal.list_groups()}
        except portal.PortalError as exc:
            return exc.as_dict()
