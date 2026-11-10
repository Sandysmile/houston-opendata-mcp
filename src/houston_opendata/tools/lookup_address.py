"""Tool: look up a Houston street address (Ask Houston+ only)."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from houston_opendata import gis, portal


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_lookup_address",
        annotations={
            "title": "Look up a Houston address",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_lookup_address(
        address: Annotated[str, "Street address, such as 901 Bagby St."],
    ) -> dict[str, Any]:
        """Find a street address in the City's address points, then report whether
        it is inside city limits, its council district, and its super neighborhood.

        Uses City of Houston GIS layers on ArcGIS Online. Use this whenever a
        question gives a street address; a ZIP code alone can cross district lines.
        """
        try:
            return await gis.lookup_address(address)
        except portal.PortalError as exc:
            return exc.as_dict()
