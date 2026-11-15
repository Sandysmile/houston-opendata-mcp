"""Tool: air quality for a Houston ZIP code (Ask Houston+ only)."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from houston_opendata import conditions, portal
from houston_opendata.models import ZipCode
from houston_opendata.tool_docs import TOOL_DESCRIPTIONS


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_air_quality",
        description=TOOL_DESCRIPTIONS["houston_air_quality"],
        annotations={
            "title": "Houston air quality",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_air_quality(
        zip_code: ZipCode | None = None,
    ) -> dict[str, Any]:
        try:
            return await conditions.air_quality(zip_code)
        except portal.PortalError as exc:
            return exc.as_dict()
