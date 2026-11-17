"""Ask Houston+ address lookup, against canned ArcGIS responses."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from houston_opendata import agent, gis, portal

ADDRESS_FIELDS = {
    "fields": [
        {"name": "OBJECTID", "type": "esriFieldTypeOID"},
        {"name": "FULLADDRESS", "type": "esriFieldTypeString"},
    ]
}


@pytest.fixture
def arcgis(monkeypatch):
    calls: list[tuple[str, dict]] = []
    responses: dict = {
        gis.ADDRESS_LAYER: ADDRESS_FIELDS,
        f"{gis.ADDRESS_LAYER}/query": {
            "features": [
                {
                    "attributes": {"FULLADDRESS": "901 BAGBY ST", "OBJECTID": 7},
                    "geometry": {"x": -95.369, "y": 29.760},
                }
            ]
        },
        f"{gis.CITY_LIMITS_LAYER}/query": {
            "features": [{"attributes": {"TYPE": "Full Service", "Shape__Area": 1}}]
        },
        f"{gis.COUNCIL_LAYER}/query": {"features": [{"attributes": {"DISTRICT": "I"}}]},
        f"{gis.SUPER_NEIGHBORHOOD_LAYER}/query": {
            "features": [{"attributes": {"SNBNAME": "DOWNTOWN", "FID": 3}}]
        },
    }

    async def fake_get(path, params):
        calls.append((path, dict(params)))
        return responses[path]

    monkeypatch.setattr(gis, "_get", fake_get)
    monkeypatch.setattr(gis, "_address_field", None)
    return calls, responses


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("901 Bagby St", "901 BAGBY ST"),
        ("901 Bagby Street, Houston, TX 77002", "901 BAGBY ST"),
        ("901 bagby st houston tx 77002", "901 BAGBY ST"),
        ("1200 Houston Ave", "1200 HOUSTON AVE"),
        ("5 N. Main St.", "5 N MAIN ST"),
        ("123 Main' OR 1=1--", "123 MAIN OR 1 1--"),
    ],
)
def test_addresses_are_normalized_and_quote_free(typed, expected):
    assert gis.normalize_address(typed) == expected


@pytest.mark.parametrize("bad", ["", "Bagby St", "x" * 200])
def test_non_addresses_are_rejected_before_any_request(arcgis, bad):
    calls, _ = arcgis
    with pytest.raises(portal.PortalError):
        gis.normalize_address(bad)
    assert calls == []


async def test_lookup_finds_district_and_super_neighborhood(arcgis):
    calls, _ = arcgis
    result = await gis.lookup_address("901 Bagby Street, Houston, TX")

    assert result["found"] is True
    assert result["matched_address"] == "901 BAGBY ST"
    assert result["inside_city_limits"] is True
    assert result["council_district"] == {"DISTRICT": "I"}
    assert result["super_neighborhood"] == {"SNBNAME": "DOWNTOWN"}
    assert "at-large" in result["note"]
    where = calls[1][1]["where"]
    assert where == "UPPER(FULLADDRESS) LIKE '901 BAGBY ST%'"


async def test_pending_city_limits_count_as_outside(arcgis):
    _, responses = arcgis
    responses[f"{gis.CITY_LIMITS_LAYER}/query"] = {
        "features": [{"attributes": {"TYPE": "Pending"}}]
    }
    result = await gis.lookup_address("901 Bagby St")
    assert result["inside_city_limits"] is False
    assert result["council_district"] is None


async def test_unknown_address_returns_a_hint(arcgis):
    _, responses = arcgis
    responses[f"{gis.ADDRESS_LAYER}/query"] = {"features": []}
    result = await gis.lookup_address("1 Nowhere Ln")
    assert result["found"] is False
    assert "hint" in result


def _addresses(*rows):
    """Address-layer features: (address, x, y) tuples."""
    return {
        "features": [
            {"attributes": {"FULLADDRESS": a}, "geometry": {"x": x, "y": y}}
            for a, x, y in rows
        ]
    }


async def test_exact_match_wins_over_longer_prefix_matches(arcgis):
    _, responses = arcgis
    # The service returns the unit first; the exact address must still win.
    responses[f"{gis.ADDRESS_LAYER}/query"] = _addresses(
        ("100 MAIN ST UNIT 2", -95.1, 29.1),
        ("100 MAIN ST", -95.2, 29.2),
    )
    result = await gis.lookup_address("100 Main Street, Houston, TX 77002")
    assert result["found"] is True
    assert result["match_type"] == "exact"
    assert result["matched_address"] == "100 MAIN ST"
    assert result["location"] == {"longitude": -95.2, "latitude": 29.2}
    assert result["other_matches"] == ["100 MAIN ST UNIT 2"]


async def test_ambiguous_address_returns_choices_instead_of_guessing(arcgis):
    calls, responses = arcgis
    responses[f"{gis.ADDRESS_LAYER}/query"] = _addresses(
        ("100 MAIN ST UNIT 1", -95.1, 29.1),
        ("100 MAIN ST UNIT 2", -95.2, 29.2),
    )
    result = await gis.lookup_address("100 Main St")
    assert result["found"] is False
    assert result["ambiguous"] is True
    assert result["candidates"] == ["100 MAIN ST UNIT 1", "100 MAIN ST UNIT 2"]
    assert "Ask the user" in result["hint"]
    assert "council_district" not in result
    # No boundary layer was queried for a guessed point.
    assert [c[0] for c in calls] == [gis.ADDRESS_LAYER, f"{gis.ADDRESS_LAYER}/query"]


async def test_single_prefix_candidate_is_used(arcgis):
    _, responses = arcgis
    responses[f"{gis.ADDRESS_LAYER}/query"] = _addresses(
        ("901 BAGBY ST STE 100", -95.369, 29.760)
    )
    result = await gis.lookup_address("901 Bagby St")
    assert result["found"] is True
    assert result["match_type"] == "only_candidate"
    assert result["other_matches"] == []


async def test_nonexistent_address_is_not_found(arcgis):
    calls, responses = arcgis
    responses[f"{gis.ADDRESS_LAYER}/query"] = {"features": []}
    result = await gis.lookup_address("99999 Nowhere Ln")
    assert result["found"] is False
    assert "ambiguous" not in result
    assert result["searched_for"] == "99999 NOWHERE LN"
    assert len(calls) == 2  # field list and address search only


def test_address_tool_only_in_ask_houston_plus():
    names = {t["name"] for t in agent.tools(use_arcgis=False)}
    assert "houston_lookup_address" not in names
    plus = {t["name"] for t in agent.tools(use_arcgis=True)}
    assert "houston_lookup_address" in plus


def test_address_tool_is_refused_when_switched_off():
    output = json.loads(
        agent.run_tool("houston_lookup_address", {"address": "901 Bagby St"})
    )
    assert "error" in output


def test_prompt_carries_todays_date():
    prompt = agent.system_prompt(now=datetime(2026, 11, 10))
    assert "Tuesday, November 10, 2026" in prompt
    assert "houston_lookup_address" not in prompt
    assert "houston_lookup_address" in agent.system_prompt(use_arcgis=True)
