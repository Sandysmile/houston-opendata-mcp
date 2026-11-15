"""Tool: look up a Houston street address (Ask Houston+ only)."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import gis, portal
from houston_opendata.models import StreetAddress
from houston_opendata.tool_docs import TOOL_DESCRIPTIONS


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_lookup_address",
        description=TOOL_DESCRIPTIONS["houston_lookup_address"],
        annotations={
            "title": "Look up a Houston address",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_lookup_address(
        address: StreetAddress,
    ) -> dict[str, Any]:
        try:
            return await gis.lookup_address(address)
        except portal.PortalError as exc:
            return exc.as_dict()
