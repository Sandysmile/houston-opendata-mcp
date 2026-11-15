"""Tool: look up a Houston street address (Ask Houston+ only)."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import gis, portal
from houston_opendata.models import StreetAddress


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
        address: StreetAddress,
    ) -> dict[str, Any]:
        """Answer "who represents me, and what neighborhood am I in?" for a street
        address: whether it is inside city limits, its council district, and its
        super neighborhood.

        Matches the address against the City's official address points, then
        checks the point against three City boundary layers in parallel, so one
        call replaces five GIS queries. Uses City of Houston GIS layers on ArcGIS
        Online. Use this whenever a
        question gives a street address; a ZIP code alone can cross district lines.
        """
        try:
            return await gis.lookup_address(address)
        except portal.PortalError as exc:
            return exc.as_dict()
