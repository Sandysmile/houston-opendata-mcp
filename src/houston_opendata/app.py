"""Houston Open Data MCP server: builds the FastMCP instance and picks a transport.

Tools, prompts, resources, and routes live in their own submodules.
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from houston_opendata.config import settings
from houston_opendata.prompts import register_prompts
from houston_opendata.resources import register_resources
from houston_opendata.routes import register_routes
from houston_opendata.tools import register_tools

mcp = FastMCP(
    name="Houston Open Data",
    instructions=(
        "Read-only access to public datasets on the City of Houston Open Data "
        "portal. Search the catalog, open a dataset, describe a table, then query "
        "its rows. Report when the portal lacks the requested data, and cite the "
        "portal_url of every dataset you use."
    ),
)

register_tools(mcp)
register_prompts(mcp)
register_resources(mcp)
register_routes(mcp)


def create_http_app():
    """Build the ASGI app with `/mcp`, `/health`, and `/version`.

    Stateless JSON responses need no sticky sessions or long-lived streams, so
    they behave behind the proxies that hosted platforms put in front of an app.
    """
    return mcp.http_app(path="/mcp", stateless_http=True, json_response=True)


def main() -> None:
    """Start the server, choosing a transport based on the environment.

    Precedence:
      1. A platform-injected `PORT` → run HTTP on that port. Cloud hosts set this.
      2. `MCP_TRANSPORT=streamable-http` in the environment → run HTTP on
         `MCP_HOST`:`MCP_PORT` (see config.py / .env).
      3. Otherwise → stdio, which is how local clients (Claude Desktop, Claude
         Code, Zed) launch the server as a subprocess.
    """
    platform_port = os.getenv("PORT")

    if platform_port:
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=int(platform_port),
            stateless_http=True,
            json_response=True,
        )
    elif settings.mcp_transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=settings.mcp_host,
            port=settings.mcp_port,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
