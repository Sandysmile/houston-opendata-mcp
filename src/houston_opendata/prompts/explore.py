"""Conversation starters for working with the portal."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the portal prompts with the MCP server."""

    @mcp.prompt()
    def explore_houston_topic(topic: str) -> str:
        """Find and assess Houston open data on a topic.

        Args:
            topic: Subject to investigate, such as "civic clubs" or "permits".
        """
        return (
            f"Find City of Houston open data about {topic}. Search the catalog, "
            "open the most relevant datasets, and tell me who publishes each one, "
            "how current it is, and which columns it has. Cite portal links, and "
            "say clearly when the portal does not contain what I asked for."
        )

    @mcp.prompt()
    def compare_by_geography(topic: str, geography: str = "council district") -> str:
        """Compare a Houston measure across a geography.

        Args:
            topic: What to compare, such as "residential building permits".
            geography: A shared key, such as "council district" or "zip code".
        """
        return (
            f"Compare {topic} across Houston by {geography}. Read the join keys "
            "resource, find datasets carrying that key, and confirm the column "
            "exists before querying. If a dataset lacks the key, say so and do not "
            "estimate. Show the numbers and link to the source datasets."
        )
