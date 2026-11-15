"""Tool: see what the portal covers — departments and topics, largest first."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from houston_opendata import portal
from houston_opendata.tool_docs import TOOL_DESCRIPTIONS


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_browse_catalog",
        description=TOOL_DESCRIPTIONS["houston_browse_catalog"],
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
        try:
            return await portal.browse_catalog(include_empty)
        except portal.PortalError as exc:
            return exc.as_dict()
