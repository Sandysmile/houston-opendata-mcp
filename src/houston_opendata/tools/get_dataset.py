"""Tool: fetch one dataset's metadata and resources."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from houston_opendata import portal


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="houston_get_dataset",
        annotations={
            "title": "Get a Houston dataset",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def houston_get_dataset(
        dataset: Annotated[str, "Dataset `name` or `id` from a search result."],
    ) -> dict[str, Any]:
        """Get a dataset's description, owner, license, and resources.

        A dataset can hold several resources (for example one per year). Each
        resource reports `queryable`: when true, use its `id` with
        houston_describe_table and houston_query_records; when false, use its
        `download_url`. `last_modified` gives the resource's as-of date.
        """
        try:
            return await portal.get_dataset(dataset)
        except portal.PortalError as exc:
            return exc.as_dict()
