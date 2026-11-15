"""Tool: weather forecast for a Houston ZIP code (Ask Houston+ only)."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from houston_opendata import conditions, portal
from houston_opendata.models import ZipCode


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_weather_forecast",
        annotations={
            "title": "Houston weather forecast",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_weather_forecast(
        zip_code: ZipCode | None = None,
        periods: Annotated[
            int,
            Field(ge=1, le=14, description="Day and night periods to return, 1-14."),
        ] = 6,
    ) -> dict[str, Any]:
        """Get the National Weather Service forecast and any active weather alerts,
        such as flood warnings, for a ZIP code in the City of Houston.

        Use for questions about weather, rain, temperature, storms, or outdoor
        plans. Only the 118 ZIP codes fully or partially within the City are
        covered; others return found=false.
        """
        try:
            return await conditions.weather_forecast(zip_code, periods)
        except portal.PortalError as exc:
            return exc.as_dict()
