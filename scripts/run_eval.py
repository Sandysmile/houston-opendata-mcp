"""Collect evaluation evidence for Ask Houston and Ask Houston+.

Run from the repository folder:

    python -m uv run python scripts/run_eval.py

It calls the real tools against the live portal and City GIS layers, then writes
eval/results.md with:

  1. Known answers for the agent questions, with portal links to confirm by hand.
  2. Response times for every tool over 10 calls each.

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

from houston_opendata import conditions  # noqa: E402
from houston_opendata.app import mcp  # noqa: E402

RUNS = 10
TEST_ADDRESS = "901 Bagby St"  # Houston City Hall, a public building
TEST_ZIP = "77002"  # Downtown
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


async def timed_uncached(client: Client, tool: str, args: dict) -> dict[str, Any]:
    """Like timed(), but clear the weather and air cache first, so the first call
    measures the live services and the rest measure the server's cache."""
    conditions._cache.clear()
    result = await timed(client, tool, args)
    result["tool"] += " *"
    return result


def years_in(text: str) -> list[int]:
    return [int(y) for y in re.findall(r"(?:FY\s?)?(20\d{2})", text or "")]


async def known_answers(
    client: Client,
) -> tuple[list[str], str | None, str | None, str | None]:
    lines: list[str] = []
    payroll_resource = None
    payroll_columns: list[str] = []
    payroll_name = None

    # Q1. Department with the most datasets
    orgs = (await call(client, "houston_browse_catalog")).get("departments", [])
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
        payroll_name = payroll[0]["name"]
        dataset = await call(client, "houston_get_dataset", {"dataset": payroll_name})
        # One call: get_dataset picks the newest table and lists its columns.
        newest = dataset.get("newest_queryable_resource") or {}
        table = next(
            (r for r in dataset.get("resources", []) if r["id"] == newest.get("id")),
            None,
        )
        if table:
            payroll_resource = table["id"]
            payroll_columns = [c["name"] for c in table.get("columns") or []]
            answer = (
                f"[{table.get('name')}]({table.get('portal_url')}), chosen by "
                f"{newest.get('chosen_by')}: {table.get('total_records')} rows; "
                f"columns: {', '.join(payroll_columns)}"
            )
    lines.append(
        f"| 2 | What columns does the most recent Payroll table have, and how many "
        f"rows? | {answer} |"
    )

    # Q3. Datasets that include council district data
    council = await call(
        client, "houston_search_datasets", {"query": "council district"}
    )
    # List the titles: keyword search can return false matches (such as Property
    # Tax), which need to be checked by hand.
    titles = "; ".join(d["title"] for d in council.get("datasets", []))
    lines.append(
        f"| 3 | How many datasets include council district data? | "
        f'{council.get("total")} results for "council district" ({titles}). '
        "Check each by hand: some only mention the words. |"
    )

    # Q4. Newest budget year
    budget = await call(
        client,
        "houston_search_datasets",
        {"query": "budget", "pagination": {"limit": 100}},
    )
    # Look inside each dataset too: yearly tables (Budget 2018 ... Budget 2025)
    # are resources of one dataset, so titles alone miss them.
    found = []
    for d in budget.get("datasets", []):
        found += [(y, d["title"], d.get("portal_url")) for y in years_in(d["title"])]
        if "budget" not in d.get("title", "").lower():
            continue
        detail = await call(client, "houston_get_dataset", {"dataset": d["name"]})
        for r in detail.get("resources", []):
            found += [
                (y, f"{d['title']}: {r.get('name')}", r.get("portal_url"))
                for y in years_in(r.get("name", ""))
            ]
    if found:
        year, where, url = max(found)
        answer = f"{year} ([{where}]({url}))"
    else:
        answer = "No year found in budget dataset or table names"
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

    # Q7. Summary mode: a count by group, computed on the server
    # Prefer a department name column over a numeric department ID.
    candidates = [c for c in payroll_columns if "DEP" in c.upper()]
    department = next(
        (c for c in candidates if "NAME" in c.upper()),
        candidates[0] if candidates else None,
    )
    if payroll_resource and department:
        summary = await call(
            client,
            "houston_query_records",
            {
                "resource_id": payroll_resource,
                "summary": {"count_by": department, "top": 3},
            },
        )
        top3 = ", ".join(
            f"{g['value']} ({g['count']:,})" for g in summary.get("groups", [])
        )
        answer = (
            f"{top3}; {summary.get('rows_read'):,} of "
            f"{summary.get('rows_matched'):,} rows read, complete: "
            f"{summary.get('complete')}"
        )
    else:
        answer = "Payroll table or department column not found"
    lines.append(
        "| 7 | Which three departments have the most employees on the newest "
        f"payroll? | {answer} |"
    )

    # Q8. Ask Houston+: weather and air quality together
    weather = await call(client, "houston_weather_forecast", {"zip_code": TEST_ZIP})
    air = await call(client, "houston_air_quality", {"zip_code": TEST_ZIP})
    first = (weather.get("periods") or [{}])[0]
    alerts = [a.get("event") for a in weather.get("active_alerts") or []]
    now = (air.get("current") or [{}])[0]
    air_text = (
        f"AQI {now.get('aqi')} ({now.get('category')})"
        if "error" not in air
        else f"air quality error: {air.get('error')} {air.get('hint', '')}"
    )
    answer = (
        f"{first.get('name')}: {first.get('summary')}, {first.get('temperature')}"
        f"°{first.get('temperature_unit')}, rain {first.get('chance_of_rain_percent')}"
        f"%; alerts: {', '.join(a for a in alerts if a) or 'none'}; {air_text}. "
        "Changes hourly: compare with the agent's answer at the same time."
        if "error" not in weather
        else f"Weather error: {weather.get('error')}"
    )
    lines.append(
        f"| 8 (Ask Houston+) | Is it a good time to be outside in {TEST_ZIP}? | "
        f"{answer} |"
    )
    return lines, payroll_resource, payroll_name, department


async def main() -> None:
    async with Client(mcp) as client:
        print("Collecting known answers...")
        answers, payroll_resource, payroll_name, department = await known_answers(
            client
        )

        print(f"Timing tools ({RUNS} calls each)...")
        perf = [
            await timed(client, "houston_search_datasets", {"query": "budget"}),
            await timed(client, "houston_browse_catalog", {}),
            await timed(client, "houston_lookup_address", {"address": TEST_ADDRESS}),
            await timed_uncached(
                client, "houston_weather_forecast", {"zip_code": TEST_ZIP}
            ),
            await timed_uncached(client, "houston_air_quality", {"zip_code": TEST_ZIP}),
        ]
        if payroll_name:
            perf.insert(
                2, await timed(client, "houston_get_dataset", {"dataset": payroll_name})
            )
        if payroll_resource:
            records = await timed(
                client,
                "houston_query_records",
                {"resource_id": payroll_resource, "pagination": {"limit": 5}},
            )
            records["tool"] += " (records, 5 rows)"
            perf.insert(3, records)
        if payroll_resource and department:
            # Summary mode reads every matching row in pages, so it is timed on
            # its own rather than inferred from the 5-row records call above.
            summary = await timed(
                client,
                "houston_query_records",
                {
                    "resource_id": payroll_resource,
                    "summary": {"count_by": department, "top": 3},
                },
            )
            summary["tool"] += " (summary, all payroll rows)"
            perf.insert(4, summary)

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
            "\\* Weather and air quality responses are cached briefly on the "
            "server, so the first call measures the live National Weather Service "
            "and AirNow, and later calls measure the cache.",
            "",
        ]
    )
    OUT.write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
