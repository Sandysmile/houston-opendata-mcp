"""Tool behavior against canned CKAN responses, through a real MCP client."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from houston_opendata import portal
from houston_opendata.app import mcp
from houston_opendata.utils import UpstreamServiceError

RESOURCE_ID = "45ddcd98-a432-4583-99cb-5e018ed5367c"
DATASET = {
    "id": "abc",
    "name": "payroll",
    "title": "Payroll",
    "notes": "Payroll data",
    "organization": {"title": "Finance"},
    "groups": [{"title": "Finance"}],
    "tags": [{"name": "pay"}],
    "metadata_modified": "2026-01-01T00:00:00",
    "license_title": "Public",
    "resources": [
        {
            "id": RESOURCE_ID,
            "name": "Payroll 2025",
            "format": "CSV",
            "datastore_active": True,
            "url": "https://data.houstontx.gov/x.csv",
        },
        {"id": "r2", "name": "Map", "format": "ArcGIS", "datastore_active": False},
    ],
}


@pytest.fixture
def ckan(monkeypatch):
    calls: list[tuple[str, dict]] = []
    responses: dict = {}

    async def fake_fetch(action, params=None, **_):
        calls.append((action, params or {}))
        response = responses[action]
        if isinstance(response, Exception):
            raise response
        return {"success": True, "result": response}

    monkeypatch.setattr(portal, "fetch_json", fake_fetch)
    return calls, responses


async def call(tool: str, args: dict | None = None) -> dict:
    async with Client(mcp) as client:
        result = await client.call_tool(tool, args or {})
    return json.loads(result.content[0].text)


async def test_search_builds_filters_and_paginates(ckan):
    calls, responses = ckan
    responses["package_search"] = {"count": 3, "results": [DATASET]}
    data = await call(
        "houston_search_datasets",
        {"query": "pay", "organization": "finance", "pagination": {"limit": 1}},
    )
    assert calls[0][1] == {
        "q": "pay",
        "rows": 1,
        "start": 0,
        "fq": 'organization:"finance"',
    }
    assert data["total"] == 3
    assert data["has_more"] is True
    assert data["next_offset"] == 1
    assert data["datasets"][0]["queryable_resource_count"] == 1


async def test_filter_injection_is_rejected_before_any_request(ckan):
    calls, _ = ckan
    data = await call(
        "houston_search_datasets", {"organization": 'x" OR private:"true'}
    )
    assert "hint" in data
    assert calls == []


async def test_get_dataset_marks_queryable_resources(ckan):
    _, responses = ckan
    responses["package_show"] = DATASET
    data = await call("houston_get_dataset", {"dataset": "payroll"})
    assert [r["queryable"] for r in data["resources"]] == [True, False]


async def test_query_encodes_filters_and_hides_internal_columns(ckan):
    calls, responses = ckan
    responses["datastore_search"] = {
        "total": 1,
        "records": [{"_id": 1, "NAME": "x" * 3000, "_full_text": "y", "rank": 0.1}],
    }
    data = await call(
        "houston_query_records",
        {"resource_id": RESOURCE_ID, "filters": {"DEPT": "HITS"}, "sort": "NAME asc"},
    )
    assert json.loads(calls[0][1]["filters"]) == {"DEPT": "HITS"}
    row = data["records"][0]
    assert "_full_text" not in row and "rank" not in row
    assert row["NAME"].endswith("[truncated]")
    assert data["has_more"] is False


@pytest.mark.parametrize("bad", ["../secrets", "not-a-uuid", "http://169.254.169.254"])
async def test_bad_resource_id_never_reaches_the_portal(ckan, bad):
    calls, _ = ckan
    data = await call("houston_query_records", {"resource_id": bad})
    assert "hint" in data
    assert calls == []


async def test_upstream_failure_returns_actionable_hint(ckan):
    _, responses = ckan
    responses["datastore_search"] = UpstreamServiceError(
        "Upstream service returned status 404."
    )
    data = await call("houston_describe_table", {"resource_id": RESOURCE_ID})
    assert data["error"] == "Upstream service returned status 404."
    assert "queryable" in data["hint"]


async def test_catalog_listing_pages_past_the_ckan_cap(ckan):
    calls, responses = ckan
    first = [{"name": f"org-{i}", "title": f"Org {i}"} for i in range(25)]

    async def paged(action, params=None, **_):
        calls.append((action, params))
        batch = first if params["offset"] == 0 else [{"name": "last", "title": "Last"}]
        return {"success": True, "result": batch}

    portal.fetch_json = paged  # restored by the fixture's monkeypatch
    data = await call("houston_list_organizations")
    assert len(data["organizations"]) == 26
    assert [c[1]["offset"] for c in calls] == [0, 25]


async def test_join_keys_resource_is_readable():
    async with Client(mcp) as client:
        contents = await client.read_resource("houston://docs/join-keys")
    assert "super neighborhood" in contents[0].text
