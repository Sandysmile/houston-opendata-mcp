"""Tool: weather forecast for a Houston ZIP code (Ask Houston+ only)."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from houston_opendata import conditions, portal
from houston_opendata.models import ZipCode
from houston_opendata.tool_docs import TOOL_DESCRIPTIONS


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_weather_forecast",
        description=TOOL_DESCRIPTIONS["houston_weather_forecast"],
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
        try:
            return await conditions.weather_forecast(zip_code, periods)
        except portal.PortalError as exc:
            return exc.as_dict()
