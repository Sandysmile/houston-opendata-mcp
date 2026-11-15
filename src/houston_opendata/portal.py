"""Read-only client for the portal's CKAN Action API.

Both the MCP tools and the Streamlit page call these functions, so what a person
sees on the page is what an agent gets. Only allow-listed read actions are used;
there is deliberately no SQL endpoint and no write action.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from houston_opendata.config import settings
from houston_opendata.utils import UpstreamServiceError, fetch_json

MAX_TEXT_CHARS = 2000
CATALOG_PAGE_SIZE = 25
CATALOG_MAX_PAGES = 20
_NAME_OR_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")
_RESOURCE_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_HIDDEN_COLUMNS = {"_full_text", "rank"}
_YEAR = re.compile(r"\b(19|20)\d{2}\b")

# get_dataset reads column lists for at most this many queryable resources.
MAX_DESCRIBED_RESOURCES = 6
SAMPLE_ROWS = 3

# Summaries read matching rows in pages, up to a fixed cap, so one question
# can't turn into an unbounded scan of the portal.
SUMMARY_PAGE_SIZE = 10_000
SUMMARY_MAX_ROWS = 100_000


class PortalError(Exception):
    """A failure carrying an actionable hint for the caller."""

    def __init__(self, error: str, hint: str) -> None:
        super().__init__(error)
        self.error = error
        self.hint = hint

    def as_dict(self) -> dict[str, str]:
        return {"error": self.error, "hint": self.hint}


async def _action(action: str, params: dict[str, Any], hint: str) -> Any:
    """Call one CKAN action and return its `result`."""
    try:
        payload = await fetch_json(action, params=params)
    except UpstreamServiceError as exc:
        raise PortalError(str(exc), hint) from None
    if not isinstance(payload, dict) or not payload.get("success"):
        raise PortalError("The portal reported that the request failed.", hint)
    return payload["result"]


def _shorten(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_TEXT_CHARS:
        return value[:MAX_TEXT_CHARS] + "… [truncated]"
    return value


def _dataset_url(name: str) -> str:
    return f"{settings.portal_url}/dataset/{name}"


def _resource_summary(resource: dict[str, Any], dataset_name: str) -> dict[str, Any]:
    resource_id = resource.get("id")
    return {
        "id": resource_id,
        "name": resource.get("name"),
        "description": _shorten(resource.get("description") or ""),
        "format": resource.get("format"),
        "queryable": bool(resource.get("datastore_active")),
        "last_modified": resource.get("last_modified") or resource.get("created"),
        "download_url": resource.get("url"),
        "portal_url": f"{_dataset_url(dataset_name)}/resource/{resource_id}",
    }


def _dataset_summary(dataset: dict[str, Any]) -> dict[str, Any]:
    name = dataset.get("name", "")
    resources = dataset.get("resources") or []
    return {
        "id": dataset.get("id"),
        "name": name,
        "title": dataset.get("title"),
        "description": _shorten(dataset.get("notes") or ""),
        "organization": (dataset.get("organization") or {}).get("title"),
        "groups": [g.get("title") for g in dataset.get("groups") or []],
        "tags": [t.get("name") for t in dataset.get("tags") or []],
        "metadata_modified": dataset.get("metadata_modified"),
        "resource_count": len(resources),
        "queryable_resource_count": sum(
            1 for r in resources if r.get("datastore_active")
        ),
        "portal_url": _dataset_url(name),
    }


def _envelope(items: list[Any], total: int, limit: int, offset: int) -> dict[str, Any]:
    next_offset = offset + len(items)
    has_more = next_offset < total and bool(items)
    return {
        "total": total,
        "count": len(items),
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
    }


async def search_datasets(
    query: str = "",
    organization: str | None = None,
    group: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    filters = []
    for field, value in (("organization", organization), ("groups", group)):
        if value:
            if not _NAME_OR_ID.match(value):
                raise PortalError(
                    f"Invalid {field} name.",
                    "Use a department or topic `name` from houston_browse_catalog, "
                    "such as a lowercase hyphenated slug.",
                )
            filters.append(f'{field}:"{value}"')
    params: dict[str, Any] = {"q": query or "*:*", "rows": limit, "start": offset}
    if filters:
        params["fq"] = " AND ".join(filters)
    result = await _action(
        "package_search",
        params,
        "Try simpler keywords, or remove the organization and group filters.",
    )
    datasets = [_dataset_summary(d) for d in result.get("results", [])]
    return {
        "datasets": datasets,
        **_envelope(datasets, int(result.get("count", 0)), limit, offset),
    }


async def get_dataset(dataset: str) -> dict[str, Any]:
    if not _NAME_OR_ID.match(dataset):
        raise PortalError(
            "Invalid dataset identifier.",
            "Use the `name` or `id` returned by houston_search_datasets.",
        )
    result = await _action(
        "package_show",
        {"id": dataset},
        "Check the identifier with houston_search_datasets.",
    )
    name = result.get("name", dataset)
    resources = [_resource_summary(r, name) for r in result.get("resources", [])]
    newest = _newest_queryable(resources)

    # Read columns and row counts for the queryable resources, newest first,
    # so the agent can go straight to houston_query_records.
    queryable = sorted(
        (r for r in resources if r["queryable"]), key=_recency, reverse=True
    )
    described = queryable[:MAX_DESCRIBED_RESOURCES]
    tables = await asyncio.gather(*(_table_or_none(r["id"]) for r in described))
    for resource, table in zip(described, tables, strict=True):
        if table:
            resource["total_records"] = table["total_records"]
            resource["columns"] = table["columns"]
    skipped = len(queryable) - len(described)

    return {
        **_dataset_summary(result),
        "license": result.get("license_title"),
        "maintainer": result.get("maintainer") or result.get("author"),
        "newest_queryable_resource": newest,
        "resources": resources,
        **(
            {
                "note": f"Columns shown for the {len(described)} newest queryable "
                f"resources. For the other {skipped}, use houston_describe_table."
            }
            if skipped
            else {}
        ),
    }


def _recency(resource: dict[str, Any]) -> tuple[int, str]:
    """Sort key: a year in the resource name (Payroll 2026), then last_modified.

    Yearly tables are often re-uploaded together, so the year in the name is a
    better guide to "newest" than the upload date.
    """
    years = [int(m.group(0)) for m in _YEAR.finditer(resource.get("name") or "")]
    return (max(years) if years else 0, str(resource.get("last_modified") or ""))


def _newest_queryable(resources: list[dict[str, Any]]) -> dict[str, Any] | None:
    queryable = [r for r in resources if r["queryable"]]
    if not queryable:
        return None
    best = max(queryable, key=_recency)
    year = _recency(best)[0]
    return {
        "id": best["id"],
        "name": best["name"],
        "chosen_by": f"year {year} in its name"
        if year
        else "most recent last_modified date",
    }


async def _table_or_none(resource_id: str) -> dict[str, Any] | None:
    """Column list for one resource; None if the portal can't describe it."""
    try:
        return await describe_table(resource_id, sample_rows=0)
    except PortalError:
        return None


def _check_resource_id(resource_id: str) -> None:
    if not _RESOURCE_ID.match(resource_id):
        raise PortalError(
            "Invalid resource_id.",
            "Use a resource `id` (a UUID) from houston_get_dataset.",
        )


_NOT_QUERYABLE_HINT = (
    "Only resources with queryable=true in houston_get_dataset can be queried. "
    "Others, such as ArcGIS services or PDFs, are reachable through download_url."
)


async def describe_table(
    resource_id: str, sample_rows: int = SAMPLE_ROWS
) -> dict[str, Any]:
    """Columns, types, row count, and a few sample rows.

    Sample rows show how values are written (HITS or Houston IT? 2026 or FY26?),
    which matters because filters in houston_query_records match exactly.
    """
    _check_resource_id(resource_id)
    result = await _action(
        "datastore_search",
        {"resource_id": resource_id, "limit": sample_rows},
        _NOT_QUERYABLE_HINT,
    )
    table: dict[str, Any] = {
        "resource_id": resource_id,
        "total_records": result.get("total"),
        "columns": [
            {"name": f.get("id"), "type": f.get("type")}
            for f in result.get("fields", [])
            if f.get("id") not in _HIDDEN_COLUMNS
        ],
    }
    if sample_rows:
        table["sample_rows"] = [
            {k: _shorten(v) for k, v in row.items() if k not in _HIDDEN_COLUMNS}
            for row in result.get("records", [])
        ]
    return table


async def query_records(
    resource_id: str,
    text: str | None = None,
    filters: dict[str, Any] | None = None,
    columns: list[str] | None = None,
    sort: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    _check_resource_id(resource_id)
    params: dict[str, Any] = {
        "resource_id": resource_id,
        "limit": limit,
        "offset": offset,
    }
    if text:
        params["q"] = text
    if filters:
        params["filters"] = json.dumps(filters)
    if columns:
        params["fields"] = ",".join(columns)
    if sort:
        params["sort"] = sort
    result = await _action(
        "datastore_search",
        params,
        "Check column names with houston_describe_table. Filters match exact "
        "values. " + _NOT_QUERYABLE_HINT,
    )
    records = [
        {k: _shorten(v) for k, v in row.items() if k not in _HIDDEN_COLUMNS}
        for row in result.get("records", [])
    ]
    return {
        "resource_id": resource_id,
        "records": records,
        **_envelope(records, int(result.get("total") or 0), limit, offset),
    }


def _number(value: Any) -> float | None:
    """Read 1234, "1,234.50", or "$1,234" as a number; None if it isn't one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


async def summarize_records(
    resource_id: str,
    count_by: str,
    sum_of: str | None = None,
    text: str | None = None,
    filters: dict[str, Any] | None = None,
    top: int = 25,
) -> dict[str, Any]:
    """Group matching rows by one column, with counts and optional sums.

    CKAN's datastore has no GROUP BY (and the SQL endpoint is deliberately not
    used), so this reads only the needed columns in large pages and adds them up
    here. It stops at SUMMARY_MAX_ROWS and says so when it does.
    """
    _check_resource_id(resource_id)
    columns = [count_by] + ([sum_of] if sum_of and sum_of != count_by else [])
    if any("," in c for c in columns):
        raise PortalError(
            "Invalid column name.",
            "Use a column name exactly as houston_describe_table lists it.",
        )

    hint = (
        "Check column names with houston_describe_table; names are case-sensitive. "
        + _NOT_QUERYABLE_HINT
    )
    groups: dict[str, dict[str, Any]] = {}
    unparsed = 0
    scanned = 0
    total = 0
    while scanned < SUMMARY_MAX_ROWS:
        params: dict[str, Any] = {
            "resource_id": resource_id,
            "fields": ",".join(columns),
            "sort": "_id asc",
            "limit": min(SUMMARY_PAGE_SIZE, SUMMARY_MAX_ROWS - scanned),
            "offset": scanned,
        }
        if text:
            params["q"] = text
        if filters:
            params["filters"] = json.dumps(filters)
        result = await _action("datastore_search", params, hint)
        total = int(result.get("total") or 0)
        records = result.get("records", [])
        for row in records:
            key = row.get(count_by)
            key = "(blank)" if key in (None, "") else str(key).strip()
            group = groups.setdefault(key, {"value": key, "count": 0, "sum": 0.0})
            group["count"] += 1
            if sum_of:
                number = _number(row.get(sum_of))
                if number is None:
                    unparsed += 1
                else:
                    group["sum"] += number
        scanned += len(records)
        if not records or scanned >= total:
            break

    ranked = sorted(groups.values(), key=lambda g: (-g["count"], g["value"]))
    shown = []
    for group in ranked[:top]:
        entry: dict[str, Any] = {"value": group["value"], "count": group["count"]}
        if sum_of:
            entry["sum"] = round(group["sum"], 2)
            entry["average"] = round(group["sum"] / group["count"], 2)
        shown.append(entry)

    complete = scanned >= total
    summary: dict[str, Any] = {
        "resource_id": resource_id,
        "count_by": count_by,
        "sum_of": sum_of,
        "rows_matched": total,
        "rows_read": scanned,
        "complete": complete,
        "total_groups": len(groups),
        "groups": shown,
    }
    notes = []
    if not complete:
        notes.append(
            f"Read the first {scanned:,} of {total:,} matching rows; totals are "
            "partial. Add filters to narrow the question."
        )
    if len(groups) > top:
        notes.append(f"Showing the {top} largest of {len(groups)} groups.")
    if sum_of and unparsed:
        summary["values_not_numeric"] = unparsed
        notes.append(
            f"{unparsed} {sum_of} values weren't numbers and were left out of "
            "sums and averages (counts include them)."
        )
    if notes:
        summary["note"] = " ".join(notes)
    return summary


async def browse_catalog(include_empty: bool = False) -> dict[str, Any]:
    """Departments and topic groups, largest first, in one call."""
    organizations, topics = await asyncio.gather(list_organizations(), list_groups())

    def rank(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept = [i for i in items if include_empty or (i.get("dataset_count") or 0)]
        return sorted(kept, key=lambda i: -(i.get("dataset_count") or 0))

    departments, groups = rank(organizations), rank(topics)
    hidden = len(organizations) + len(topics) - len(departments) - len(groups)
    catalog: dict[str, Any] = {
        "departments": departments,
        "topics": groups,
        "how_to_use": "Pass a department `name` as `organization`, or a topic "
        "`name` as `group`, to houston_search_datasets.",
    }
    if hidden:
        catalog["note"] = (
            f"{hidden} departments or topics with no datasets are hidden; "
            "set include_empty to see them."
        )
    return catalog


async def _list_catalog(action: str) -> list[dict[str, Any]]:
    # CKAN caps all_fields listings (25 by default), so page until a short page.
    result: list[dict[str, Any]] = []
    for page in range(CATALOG_MAX_PAGES):
        batch = await _action(
            action,
            {
                "all_fields": "true",
                "include_dataset_count": "true",
                "limit": CATALOG_PAGE_SIZE,
                "offset": page * CATALOG_PAGE_SIZE,
            },
            "The portal may be temporarily unavailable; retry shortly.",
        )
        result.extend(batch)
        if len(batch) < CATALOG_PAGE_SIZE:
            break
    return [
        {
            "name": item.get("name"),
            "title": item.get("title") or item.get("display_name"),
            "description": _shorten(item.get("description") or ""),
            "dataset_count": item.get("package_count"),
        }
        for item in result
    ]


async def list_organizations() -> list[dict[str, Any]]:
    return await _list_catalog("organization_list")


async def list_groups() -> list[dict[str, Any]]:
    return await _list_catalog("group_list")
