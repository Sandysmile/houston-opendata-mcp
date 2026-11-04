"""Read-only client for the portal's CKAN Action API.

Both the MCP tools and the Streamlit page call these functions, so what a person
sees on the page is what an agent gets. Only allow-listed read actions are used;
there is deliberately no SQL endpoint and no write action.
"""

from __future__ import annotations

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
                    "Use the `name` value from houston_list_organizations or "
                    "houston_list_groups, such as a lowercase hyphenated slug.",
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
    return {
        **_dataset_summary(result),
        "license": result.get("license_title"),
        "maintainer": result.get("maintainer") or result.get("author"),
        "resources": [_resource_summary(r, name) for r in result.get("resources", [])],
    }


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


async def describe_table(resource_id: str) -> dict[str, Any]:
    _check_resource_id(resource_id)
    result = await _action(
        "datastore_search",
        {"resource_id": resource_id, "limit": 0},
        _NOT_QUERYABLE_HINT,
    )
    return {
        "resource_id": resource_id,
        "total_records": result.get("total"),
        "columns": [
            {"name": f.get("id"), "type": f.get("type")}
            for f in result.get("fields", [])
            if f.get("id") not in _HIDDEN_COLUMNS
        ],
    }


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
