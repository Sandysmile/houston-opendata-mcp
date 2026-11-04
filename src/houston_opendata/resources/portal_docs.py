"""Reference notes the model can read without a tool call."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the portal reference resources with the MCP server."""

    @mcp.resource("houston://info/server")
    def server_info() -> str:
        """What this server is and how its tools fit together."""
        return (
            "Read-only access to public data on the City of Houston Open Data "
            "portal (data.houstontx.gov), which runs on CKAN.\n\n"
            "Typical flow: houston_search_datasets -> houston_get_dataset -> "
            "houston_describe_table -> houston_query_records.\n\n"
            "Resources with queryable=false, such as ArcGIS services and PDFs, "
            "cannot be read row by row; use their download_url.\n\n"
            "This is a hackathon prototype, not an official City of Houston service."
        )

    @mcp.resource("houston://docs/join-keys")
    def join_keys() -> str:
        """Geographic keys used to connect Houston datasets."""
        return (
            "Standard join keys for connecting Houston datasets:\n"
            "- block group\n- census tract\n- zip code\n- street address\n"
            "- council district\n- super neighborhood\n\n"
            "Not every dataset carries every key. Column names vary, so confirm "
            "them with houston_describe_table before joining."
        )
