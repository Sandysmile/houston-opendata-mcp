"""Resources submodule — reference data the client can read directly."""

from __future__ import annotations

from houston_opendata.resources import portal_docs


def register_resources(mcp) -> None:
    """Register all resources with the MCP server."""
    portal_docs.register(mcp)


__all__ = ["register_resources"]
