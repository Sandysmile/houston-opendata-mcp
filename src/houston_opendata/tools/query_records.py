"""Tool: read rows from a queryable resource."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from houston_opendata import portal
from houston_opendata.models import PaginationParams


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_query_records",
        annotations={
            "title": "Query Houston records",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_query_records(
        resource_id: Annotated[str, "Resource `id` (UUID) from houston_get_dataset."],
        text: Annotated[
            str | None, "Full-text search across all columns in the table."
        ] = None,
        filters: Annotated[
            dict[str, Any] | None,
            'Exact matches by column, such as {"COUNCIL_DISTRICT": "K"}.',
        ] = None,
        columns: Annotated[
            list[str] | None, "Columns to return. Omit to return all of them."
        ] = None,
        sort: Annotated[
            str | None, 'Column and direction, such as "YEAR desc".'
        ] = None,
        pagination: PaginationParams | None = None,
    ) -> dict[str, Any]:
        """Read rows from a queryable resource, with filters and pagination.

        Returns at most 100 rows per call. Use `total` to count matches without
        paging through them, for example with a limit of 1. There is no server-side
        aggregation, so for sums or averages over many rows, page through
        `next_offset`. Very long text values are truncated.
        """
        page = pagination or PaginationParams()
        try:
            return await portal.query_records(
                resource_id, text, filters, columns, sort, page.limit, page.offset
            )
        except portal.PortalError as exc:
            return exc.as_dict()
