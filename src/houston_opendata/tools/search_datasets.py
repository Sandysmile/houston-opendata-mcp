"""Tool: search the portal's dataset catalog."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import portal
from houston_opendata.models import CatalogName, PaginationParams, SearchText
from houston_opendata.tool_docs import TOOL_DESCRIPTIONS


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_search_datasets",
        description=TOOL_DESCRIPTIONS["houston_search_datasets"],
        annotations={
            "title": "Search Houston datasets",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_search_datasets(
        query: SearchText = "",
        organization: CatalogName | None = None,
        group: CatalogName | None = None,
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        page = pagination or PaginationParams()
        try:
            return await portal.search_datasets(
                query, organization, group, page.limit, page.offset
            )
        except portal.PortalError as exc:
            return exc.as_dict()
