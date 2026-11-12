"""Collect evaluation evidence for Ask Houston and Ask Houston+.

Run from the repository folder:

    python -m uv run python scripts/run_eval.py

It calls the real tools against the live portal and City GIS layers, then writes
eval/results.md with:

  1. Known answers for the agent questions, with portal links to confirm by hand.
  2. Response times for the main tools over 10 calls each.

It does not call an AI model. Ask the agent questions yourself in the app and
compare its answers with eval/results.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import statistics
import time
from pathlib import Path
from typing import Any

# Turn on the Ask Houston+ address tool before the server is imported.
os.environ["USE_ARCGIS"] = "true"

from fastmcp import Client  # noqa: E402

from houston_opendata.app import mcp  # noqa: E402

RUNS = 10
TEST_ADDRESS = "901 Bagby St"  # Houston City Hall, a public building
OUT = Path("eval/results.md")


async def call(client: Client, tool: str, args: dict | None = None) -> dict[str, Any]:
    result = await client.call_tool(tool, args or {})
    return json.loads(result.content[0].text)


async def timed(client: Client, tool: str, args: dict) -> dict[str, Any]:
    """Call a tool RUNS times and return timing in seconds."""
    times = []
    errors = 0
    for _ in range(RUNS):
        start = time.perf_counter()
        try:
            data = await call(client, tool, args)
            if "error" in data:
                errors += 1
        except Exception:  # noqa: BLE001 - count any failure
            errors += 1
        times.append(time.perf_counter() - start)
    return {
        "tool": tool,
        "first": times[0],
        "median": statistics.median(times),
        "max": max(times),
        "errors": errors,
    }


def years_in(text: str) -> list[int]:
    return [int(y) for y in re.findall(r"(?:FY\s?)?(20\d{2})", text or "")]


async def known_answers(client: Client) -> tuple[list[str], str | None]:
    lines: list[str] = []
    payroll_resource = None

    # Q1. Department with the most datasets
    orgs = (await call(client, "houston_list_organizations")).get("organizations", [])
    orgs = sorted(orgs, key=lambda o: o.get("dataset_count") or 0, reverse=True)
    top = ", ".join(f"{o['title']} ({o['dataset_count']})" for o in orgs[:3])
    lines.append(f"| 1 | Which department publishes the most datasets? | {top} |")

    # Q2. Newest Payroll table: columns and rows
    search = await call(
        client,
        "houston_search_datasets",
        {"query": "payroll", "pagination": {"limit": 20}},
    )
    payroll = sorted(
        search.get("datasets", []),
        key=lambda d: d.get("metadata_modified") or "",
        reverse=True,
    )
    answer = "No Payroll dataset found"
    if payroll:
        dataset = await call(
            client, "houston_get_dataset", {"dataset": payroll[0]["name"]}
        )
        tables = sorted(
            (r for r in dataset.get("resources", []) if r.get("queryable")),
            key=lambda r: r.get("last_modified") or "",
            reverse=True,
        )
        if tables:
            payroll_resource = tables[0]["id"]
            table = await call(
                client, "houston_describe_table", {"resource_id": payroll_resource}
            )
            columns = ", ".join(c["name"] for c in table.get("columns", []))
            answer = (
                f"[{tables[0].get('name')}]({tables[0].get('portal_url')}): "
                f"{table.get('total_records')} rows; columns: {columns}"
            )
    lines.append(
        f"| 2 | What columns does the most recent Payroll table have, and how many "
        f"rows? | {answer} |"
    )

    # Q3. Datasets that include council district data
    council = await call(
        client, "houston_search_datasets", {"query": "council district"}
    )
    lines.append(
        f"| 3 | How many datasets include council district data? | "
        f'{council.get("total")} (keyword search for "council district") |'
    )

    # Q4. Newest budget year
    budget = await call(
        client,
        "houston_search_datasets",
        {"query": "budget", "pagination": {"limit": 100}},
    )
    found = [
        (y, d["title"])
        for d in budget.get("datasets", [])
        for y in years_in(d.get("title", ""))
    ]
    if found:
        year, title = max(found)
        answer = f"{year} ({title})"
    else:
        answer = "No year found in budget dataset titles"
    lines.append(f"| 4 | Which budget year is the newest on the portal? | {answer} |")

    # Q5. Data the portal doesn't hold
    lines.append(
        "| 5 | What is the average commute time of City of Houston employees? | "
        "Not on the portal. The agent should say so and not invent a number. |"
    )

    # Q6. Ask Houston+ address question
    place = await call(client, "houston_lookup_address", {"address": TEST_ADDRESS})
    if place.get("found"):
        district = place.get("council_district") or {}
        hood = place.get("super_neighborhood") or {}
        answer = (
            f"Inside city limits: {place.get('inside_city_limits')}; "
            f"council district: {json.dumps(district)}; "
            f"super neighborhood: {json.dumps(hood)}"
        )
    else:
        answer = f"Address not found: {place.get('hint') or place.get('error')}"
    lines.append(
        f"| 6 (Ask Houston+) | What council district and super neighborhood is "
        f"{TEST_ADDRESS} in? | {answer} |"
    )
    return lines, payroll_resource


async def main() -> None:
    async with Client(mcp) as client:
        print("Collecting known answers...")
        answers, payroll_resource = await known_answers(client)

        print(f"Timing tools ({RUNS} calls each)...")
        perf = [
            await timed(client, "houston_search_datasets", {"query": "budget"}),
            await timed(client, "houston_lookup_address", {"address": TEST_ADDRESS}),
        ]
        if payroll_resource:
            perf.insert(
                1,
                await timed(
                    client,
                    "houston_query_records",
                    {"resource_id": payroll_resource, "pagination": {"limit": 5}},
                ),
            )

    rows = [
        f"| {p['tool']} | {p['first']:.2f} | {p['median']:.2f} | {p['max']:.2f} | "
        f"{p['errors']} |"
        for p in perf
    ]
    report = "\n".join(
        [
            "# Evaluation results",
            "",
            f"Run on {time.strftime('%Y-%m-%d %H:%M')} against the live portal "
            "and City GIS layers.",
            "",
            "## Known answers",
            "",
            "Confirm each one on data.houstontx.gov, then ask the same question "
            "in the app.",
            "",
            "| # | Question | Known answer |",
            "|---|---|---|",
            *answers,
            "",
            f"## Response times (seconds, {RUNS} calls each, run locally)",
            "",
            "| Tool | First call | Median | Slowest | Errors |",
            "|---|---|---|---|---|",
            *rows,
            "",
        ]
    )
    OUT.write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
