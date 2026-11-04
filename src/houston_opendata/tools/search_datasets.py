"""Tool: search the portal's dataset catalog."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from houston_opendata import portal
from houston_opendata.models import PaginationParams


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_search_datasets",
        annotations={
            "title": "Search Houston datasets",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_search_datasets(
        query: Annotated[
            str, "Keywords, such as 'council district'. Empty lists everything."
        ] = "",
        organization: Annotated[
            str | None, "Organization `name` from houston_list_organizations."
        ] = None,
        group: Annotated[str | None, "Group `name` from houston_list_groups."] = None,
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        """Search City of Houston open datasets by keyword, department, or topic.

        Start here. Each result's `metadata_modified` shows when its catalog entry
        last changed; update frequency varies by dataset. Results include
        harvested GIS datasets. Pass a result's `name` to houston_get_dataset.

        Returns `datasets` with `total`, `has_more`, and `next_offset`, or an
        `error` with a `hint`.
        """
        page = pagination or PaginationParams()
        try:
            return await portal.search_datasets(
                query, organization, group, page.limit, page.offset
            )
        except portal.PortalError as exc:
            return exc.as_dict()
