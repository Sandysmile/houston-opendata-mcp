"""Tool: air quality for a Houston ZIP code (Ask Houston+ only)."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from houston_opendata import conditions, portal


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_air_quality",
        annotations={
            "title": "Houston air quality",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_air_quality(
        zip_code: Annotated[
            str | None, "Houston ZIP code, such as 77002. Omit for downtown."
        ] = None,
    ) -> dict[str, Any]:
        """Get current air quality (AQI) and the air quality forecast from EPA
        AirNow for a ZIP code in the City of Houston.

        Use for questions about air quality, ozone, smog, or whether it's healthy
        to be outside. AirNow reports by area, and most Houston ZIP codes share
        one reporting area, so readings are citywide, not neighborhood-level.
        """
        try:
            return await conditions.air_quality(zip_code)
        except portal.PortalError as exc:
            return exc.as_dict()
