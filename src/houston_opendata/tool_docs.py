"""Tool descriptions: one source of truth for every client.

The MCP server (tools/*.py) and the Streamlit chat agent (agent.py) both read
these, so Claude Desktop and the app describe each tool the same way. The
Nov 15 evaluation found the app missed summary mode when it had its own shorter
copy; keep any change here, never in a second place.
"""

from __future__ import annotations

TOOL_DESCRIPTIONS: dict[str, str] = {
    "houston_air_quality": (
        "Get current air quality (AQI) and the air quality forecast from EPA\n"
        "AirNow for a ZIP code in the City of Houston.\n"
        "\n"
        "Use for questions about air quality, ozone, smog, or whether it's healthy\n"
        "to be outside. AirNow reports by area, and most Houston ZIP codes share\n"
        "one reporting area, so readings are citywide, not neighborhood-level."
    ),
    "houston_browse_catalog": (
        "See what the portal covers: which departments publish data and which\n"
        "topics it is organized by, each with its dataset count, largest first.\n"
        "\n"
        'Use for "what data does the City have?", "which department publishes the\n'
        'most?", or to find the right `organization` or `group` filter for\n'
        "houston_search_datasets. Combines the portal's department and topic\n"
        "listings, paged past the portal's 25-item cap, in one call."
    ),
    "houston_describe_table": (
        "Show a table's columns, types, row count, and three sample rows.\n"
        "\n"
        "Use before filtering when you need to see how values are written, since\n"
        'filters match exactly (is it "HITS" or "Houston IT"? "K" or "District\n'
        'K"?). houston_get_dataset already lists columns for the newest tables, so\n'
        "call this mainly for older tables or to check value formats."
    ),
    "houston_get_dataset": (
        "Open a dataset: who publishes it, how current it is, its resources, and\n"
        "the columns and row count of each queryable resource.\n"
        "\n"
        'Answers "what\'s in this dataset and which table should I query?" in one\n'
        "call. `newest_queryable_resource` picks the latest table (for example\n"
        'Payroll 2026 out of yearly tables), so "most recent" questions need no\n'
        "guessing. Resources with queryable=true go straight to\n"
        "houston_query_records; others are reachable through `download_url`."
    ),
    "houston_lookup_address": (
        'Answer "who represents me, and what neighborhood am I in?" for a street\n'
        "address: whether it is inside city limits, its council district, and its\n"
        "super neighborhood.\n"
        "\n"
        "Matches the address against the City's official address points, then\n"
        "checks the point against three City boundary layers in parallel, so one\n"
        "call replaces five GIS queries. Uses City of Houston GIS layers on ArcGIS\n"
        "Online. Use this whenever a\n"
        "question gives a street address; a ZIP code alone can cross district lines.\n"
        "\n"
        "An exact match wins. If several City addresses fit and none matches\n"
        "exactly, it returns ambiguous=true with the candidates: ask the user which\n"
        "one they mean instead of choosing."
    ),
    "houston_query_records": (
        "Answer questions about a table's records, in one of two modes.\n"
        "\n"
        'Rows: "which records match?" Returns up to 100 matching rows per call\n'
        "with `total`, filters, sorting and paging.\n"
        "\n"
        'Summary: "how many, or how much, by what?" Pass `summary` with `count_by`\n'
        "(and optionally `sum_of`) to get counts, sums and averages per group,\n"
        "such as employees and average salary by department. The server reads up\n"
        "to 100,000 matching rows itself, so don't page through rows to add them\n"
        "up. `columns`, `sort` and `pagination` are ignored in summary mode."
    ),
    "houston_search_datasets": (
        "Find City of Houston open datasets on a subject, by keyword, department\n"
        "(`organization`), or topic (`group`).\n"
        "\n"
        "Start here. Each result's `metadata_modified` shows when its catalog entry\n"
        "last changed; update frequency varies by dataset. Results include\n"
        "harvested GIS datasets. Pass a result's `name` to houston_get_dataset.\n"
        "\n"
        "Returns `datasets` with `total`, `has_more`, and `next_offset`, or an\n"
        "`error` with a `hint`."
    ),
    "houston_weather_forecast": (
        "Get the National Weather Service forecast and any active weather alerts,\n"
        "such as flood warnings, for a ZIP code in the City of Houston.\n"
        "\n"
        "Use for questions about weather, rain, temperature, storms, or outdoor\n"
        "plans. Only the 118 ZIP codes fully or partially within the City are\n"
        "covered; others return found=false."
    ),
}
