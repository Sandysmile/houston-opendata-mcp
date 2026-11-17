"""Tool behavior against canned CKAN responses, through a real MCP client."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

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


TABLE = {
    "total": 26220,
    "fields": [
        {"id": "_id", "type": "int"},
        {"id": "DEPARTMENT", "type": "text"},
        {"id": "_full_text", "type": "tsvector"},
    ],
    "records": [{"_id": 1, "DEPARTMENT": "HITS", "_full_text": "x"}],
}


async def test_get_dataset_marks_queryable_resources_and_lists_columns(ckan):
    calls, responses = ckan
    responses["package_show"] = DATASET
    responses["datastore_search"] = TABLE
    data = await call("houston_get_dataset", {"dataset": "payroll"})
    assert [r["queryable"] for r in data["resources"]] == [True, False]
    table = data["resources"][0]
    assert table["total_records"] == 26220
    assert [c["name"] for c in table["columns"]] == ["_id", "DEPARTMENT"]
    assert "columns" not in data["resources"][1]  # not queryable, not described
    # Only the queryable resource was described, with no sample rows.
    assert [c for c in calls if c[0] == "datastore_search"][0][1]["limit"] == 0


async def test_get_dataset_picks_the_newest_table_by_year_in_name(ckan):
    _, responses = ckan
    yearly = [
        {
            "id": f"00000000-0000-0000-0000-00000000{year}",
            "name": f"Payroll {year}",
            "datastore_active": True,
            # Re-uploaded together, so upload dates don't show which is newest.
            "last_modified": "2026-01-01" if year == 2024 else "2025-01-01",
        }
        for year in (2024, 2026, 2025)
    ]
    responses["package_show"] = {**DATASET, "resources": yearly}
    responses["datastore_search"] = TABLE
    data = await call("houston_get_dataset", {"dataset": "payroll"})
    assert data["newest_queryable_resource"]["name"] == "Payroll 2026"
    assert "2026" in data["newest_queryable_resource"]["chosen_by"]


async def test_get_dataset_survives_a_table_that_cannot_be_described(ckan):
    _, responses = ckan
    responses["package_show"] = DATASET
    responses["datastore_search"] = UpstreamServiceError("status 500")
    data = await call("houston_get_dataset", {"dataset": "payroll"})
    assert data["resources"][0]["queryable"] is True
    assert "columns" not in data["resources"][0]


async def test_describe_table_shows_sample_rows(ckan):
    calls, responses = ckan
    responses["datastore_search"] = TABLE
    data = await call("houston_describe_table", {"resource_id": RESOURCE_ID})
    assert calls[0][1]["limit"] == portal.SAMPLE_ROWS
    assert data["sample_rows"] == [{"_id": 1, "DEPARTMENT": "HITS"}]


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
    data = await call("houston_browse_catalog", {"include_empty": True})
    assert len(data["departments"]) == 26
    assert len(data["topics"]) == 26
    offsets = sorted(c[1]["offset"] for c in calls)
    assert offsets == [0, 0, 25, 25]  # both listings, paged past the cap


async def test_browse_catalog_ranks_and_hides_empty_entries(ckan):
    _, responses = ckan
    responses["organization_list"] = [
        {"name": "small", "title": "Small", "package_count": 2},
        {"name": "empty", "title": "Empty", "package_count": 0},
        {"name": "big", "title": "Big", "package_count": 25},
    ]
    responses["group_list"] = [
        {"name": "safety", "title": "Safety", "package_count": 4}
    ]
    data = await call("houston_browse_catalog")
    assert [d["name"] for d in data["departments"]] == ["big", "small"]
    assert [t["name"] for t in data["topics"]] == ["safety"]
    assert "1 departments or topics" in data["note"]


def _paged_rows(calls, rows, total=None):
    """A fake datastore that serves `rows` by limit and offset."""

    async def fetch(action, params=None, **_):
        calls.append((action, params))
        start, size = params["offset"], params["limit"]
        return {
            "success": True,
            "result": {
                "total": len(rows) if total is None else total,
                "records": rows[start : start + size],
            },
        }

    return fetch


async def test_summary_counts_sums_and_averages_by_group(ckan):
    calls, _ = ckan
    rows = [
        {"DEPT": "HITS", "PAY": "$1,000.50"},
        {"DEPT": "HITS", "PAY": 3000},
        {"DEPT": "HPW", "PAY": "n/a"},
        {"DEPT": "", "PAY": 10},
    ]
    portal.fetch_json = _paged_rows(calls, rows)
    data = await call(
        "houston_query_records",
        {
            "resource_id": RESOURCE_ID,
            "filters": {"YEAR": "2026"},
            "summary": {"count_by": "DEPT", "sum_of": "PAY"},
        },
    )
    assert data["complete"] is True and data["rows_read"] == 4
    hits = data["groups"][0]
    assert hits == {"value": "HITS", "count": 2, "sum": 4000.5, "average": 2000.25}
    assert {g["value"] for g in data["groups"]} == {"HITS", "HPW", "(blank)"}
    assert data["values_not_numeric"] == 1
    params = calls[0][1]
    assert params["fields"] == "DEPT,PAY"
    assert json.loads(params["filters"]) == {"YEAR": "2026"}


async def test_summary_averages_only_numeric_values_across_pages(ckan, monkeypatch):
    calls, _ = ckan
    monkeypatch.setattr(portal, "SUMMARY_PAGE_SIZE", 2)
    rows = [
        {"DEPT": "A", "PAY": 100},
        {"DEPT": "A", "PAY": None},
        {"DEPT": "A", "PAY": "n/a"},
        {"DEPT": "A", "PAY": 0},
        {"DEPT": "B", "PAY": "$300.00"},
        {"DEPT": "B", "PAY": ""},
    ]
    portal.fetch_json = _paged_rows(calls, rows)
    data = await call(
        "houston_query_records",
        {"resource_id": RESOURCE_ID, "summary": {"count_by": "DEPT", "sum_of": "PAY"}},
    )
    assert data["groups"] == [
        {"value": "A", "count": 4, "sum": 100.0, "average": 50.0},
        {"value": "B", "count": 2, "sum": 300.0, "average": 300.0},
    ]
    assert data["values_not_numeric"] == 3
    assert data["complete"] is True


async def test_summary_average_is_null_without_numeric_values(ckan):
    calls, _ = ckan
    portal.fetch_json = _paged_rows(
        calls,
        [{"DEPT": "A", "PAY": None}, {"DEPT": "A", "PAY": "n/a"}],
    )
    data = await call(
        "houston_query_records",
        {"resource_id": RESOURCE_ID, "summary": {"count_by": "DEPT", "sum_of": "PAY"}},
    )
    assert data["groups"] == [{"value": "A", "count": 2, "sum": 0.0, "average": None}]
    assert data["values_not_numeric"] == 2


async def test_summary_pages_and_stops_at_the_cap(ckan, monkeypatch):
    calls, _ = ckan
    monkeypatch.setattr(portal, "SUMMARY_PAGE_SIZE", 2)
    monkeypatch.setattr(portal, "SUMMARY_MAX_ROWS", 4)
    rows = [{"DEPT": "A"}] * 5
    portal.fetch_json = _paged_rows(calls, rows)
    data = await call(
        "houston_query_records",
        {"resource_id": RESOURCE_ID, "summary": {"count_by": "DEPT"}},
    )
    assert [c[1]["offset"] for c in calls] == [0, 2]
    assert data["complete"] is False
    assert data["rows_read"] == 4 and data["rows_matched"] == 5
    assert "partial" in data["note"]


async def test_summary_rejects_bad_input_before_any_request(ckan):
    calls, _ = ckan
    data = await call(
        "houston_query_records",
        {"resource_id": RESOURCE_ID, "summary": {"count_by": "A,B"}},
    )
    assert "hint" in data
    with pytest.raises(ToolError):  # Pydantic: top must be 1-100
        await call(
            "houston_query_records",
            {"resource_id": RESOURCE_ID, "summary": {"count_by": "A", "top": 500}},
        )
    assert calls == []


async def test_join_keys_resource_is_readable():
    async with Client(mcp) as client:
        contents = await client.read_resource("houston://docs/join-keys")
    assert "super neighborhood" in contents[0].text
