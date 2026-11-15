"""Tool: answer "which records" and "how many, by what" questions on a table."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from houston_opendata import portal
from houston_opendata.models import (
    ColumnList,
    PaginationParams,
    RecordFilters,
    ResourceId,
    SummaryParams,
)
from houston_opendata.tool_docs import TOOL_DESCRIPTIONS


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_query_records",
        description=TOOL_DESCRIPTIONS["houston_query_records"],
        annotations={
            "title": "Query Houston records",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_query_records(
        resource_id: ResourceId,
        text: Annotated[
            str | None,
            Field(max_length=200, description="Full-text search across all columns."),
        ] = None,
        filters: RecordFilters | None = None,
        summary: SummaryParams | None = None,
        columns: ColumnList | None = None,
        sort: Annotated[
            str | None,
            Field(max_length=100, description='Column and direction, "YEAR desc".'),
        ] = None,
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        try:
            if summary:
                return await portal.summarize_records(
                    resource_id,
                    summary.count_by,
                    summary.sum_of,
                    text,
                    filters,
                    summary.top,
                )
            page = pagination or PaginationParams()
            return await portal.query_records(
                resource_id, text, filters, columns, sort, page.limit, page.offset
            )
        except portal.PortalError as exc:
            return exc.as_dict()
