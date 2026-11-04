"""Prompts submodule — reusable conversation starters."""

from __future__ import annotations

from houston_opendata.prompts import explore


def register_prompts(mcp) -> None:
    """Register all prompts with the MCP server."""
    explore.register(mcp)


__all__ = ["register_prompts"]
