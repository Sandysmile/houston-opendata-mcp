"""Tool: see what the portal covers — departments and topics, largest first."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from houston_opendata import portal


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_browse_catalog",
        annotations={
            "title": "Browse the Houston catalog",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_browse_catalog(
        include_empty: Annotated[
            bool,
            Field(description="Also list departments and topics with no datasets."),
        ] = False,
    ) -> dict[str, Any]:
        """See what the portal covers: which departments publish data and which
        topics it is organized by, each with its dataset count, largest first.

        Use for "what data does the City have?", "which department publishes the
        most?", or to find the right `organization` or `group` filter for
        houston_search_datasets. Combines the portal's department and topic
        listings, paged past the portal's 25-item cap, in one call.
        """
        try:
            return await portal.browse_catalog(include_empty)
        except portal.PortalError as exc:
            return exc.as_dict()
