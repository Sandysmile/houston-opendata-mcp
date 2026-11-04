"""Check a running server with a real MCP client.

    uv run python scripts/smoke_test.py https://your-host/mcp

Exits 0 only if the handshake, tool list, and a live portal search all succeed.
"""

from __future__ import annotations

import asyncio
import sys

from fastmcp import Client

EXPECTED_TOOLS = {
    "houston_search_datasets",
    "houston_get_dataset",
    "houston_describe_table",
    "houston_query_records",
    "houston_list_organizations",
    "houston_list_groups",
}


async def run(url: str) -> int:
    async with Client(url, timeout=60) as client:
        print("PASS  MCP handshake")

        names = {tool.name for tool in await client.list_tools()}
        missing = EXPECTED_TOOLS - names
        if missing:
            print(f"FAIL  missing tools: {sorted(missing)}")
            return 1
        print(f"PASS  {len(names)} tools listed")

        result = await client.call_tool("houston_search_datasets", {"query": "budget"})
        data = result.data
        if not isinstance(data, dict) or "error" in data:
            print(f"FAIL  portal search: {data}")
            return 1
        print(f"PASS  portal search: {data['total']} datasets match 'budget'")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        sys.exit(asyncio.run(run(sys.argv[1])))
    except Exception as exc:  # noqa: BLE001 - report any connection failure plainly
        print(f"FAIL  could not reach an MCP server: {type(exc).__name__}: {exc}")
        sys.exit(1)
