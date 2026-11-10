"""Read-only client for City of Houston GIS layers on ArcGIS Online.

Used only by Ask Houston+ (USE_ARCGIS=true). Like portal.py, every layer is fixed
here, so tools never accept a URL from the caller. Errors are raised as
PortalError, so the agent and the tools handle them the same way.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from houston_opendata.portal import PortalError
from houston_opendata.utils import DEFAULT_TIMEOUT, MAX_RESPONSE_BYTES, USER_AGENT

ARCGIS_ORIGIN = "https://services.arcgis.com"
_SERVICES = "/NummVBqZSIJKUeVR/ArcGIS/rest/services"

ADDRESS_LAYER = f"{_SERVICES}/COH_SiteAddresses/FeatureServer/0"
CITY_LIMITS_LAYER = f"{_SERVICES}/City_Limits_Full/FeatureServer/0"
COUNCIL_LAYER = f"{_SERVICES}/Houston_Council_Districts_view/FeatureServer/2"
SUPER_NEIGHBORHOOD_LAYER = f"{_SERVICES}/Super_Neighborhoods/FeatureServer/0"

SOURCES = [
    {"name": "COH Site Addresses (Planning & Development)", "layer": ADDRESS_LAYER},
    {"name": "COH City Limits (Planning & Development)", "layer": CITY_LIMITS_LAYER},
    {"name": "Houston Council Districts", "layer": COUNCIL_LAYER},
    {"name": "Houston Super Neighborhoods", "layer": SUPER_NEIGHBORHOOD_LAYER},
]

MAX_MATCHES = 5
_ADDRESS_FIELD_NAMES = ("FULLADDRESS", "FULL_ADDRESS", "FULLADDR", "SITE_ADDRESS")
_SUFFIXES = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "DRIVE": "DR",
    "ROAD": "RD",
    "BOULEVARD": "BLVD",
    "LANE": "LN",
    "COURT": "CT",
    "PLACE": "PL",
    "CIRCLE": "CIR",
    "PARKWAY": "PKWY",
    "FREEWAY": "FWY",
    "HIGHWAY": "HWY",
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
}
_NOT_ALLOWED = re.compile(r"[^A-Z0-9 #/-]")
# Trailing city, state, or ZIP, such as "HOUSTON TX 77002". A street named
# Houston (1200 HOUSTON AVE) is kept because the pattern must reach the end.
_CITY_TAIL = re.compile(r"(\s+HOUSTON)?(\s+(TX|TEXAS))?(\s+\d{5}(-\d{4})?)?\s*$")
_address_field: str | None = None

_ADDRESS_HINT = (
    "Give a Houston street address with a house number, such as 901 Bagby St."
)
_GIS_HINT = "The City GIS service may be busy. Try again shortly."


def normalize_address(text: str) -> str:
    """Turn user input into the City's address style, such as `901 BAGBY ST`.

    Raises PortalError for input that isn't a street address. The result holds
    only letters, digits, spaces, and `# / -`, so it is safe inside a quoted
    LIKE pattern.
    """
    value = (text or "").upper().split(",")[0].replace(".", "")
    value = _NOT_ALLOWED.sub(" ", value)
    value = _CITY_TAIL.sub("", " ".join(value.split()), count=1)
    words = [_SUFFIXES.get(word, word) for word in value.split()]
    value = " ".join(words)
    if not value or not value[0].isdigit() or not 3 <= len(value) <= 80:
        raise PortalError("That doesn't look like a street address.", _ADDRESS_HINT)
    return value


async def _get(path: str, params: dict[str, Any]) -> Any:
    """GET one fixed ArcGIS REST path and return parsed JSON."""
    try:
        async with httpx.AsyncClient(
            base_url=ARCGIS_ORIGIN,
            follow_redirects=False,
            timeout=DEFAULT_TIMEOUT,
            trust_env=False,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            async with client.stream("GET", path, params=params) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise PortalError("City GIS response was too large.", _GIS_HINT)
                payload = json.loads(content)
    except PortalError:
        raise
    except httpx.HTTPStatusError as exc:
        raise PortalError(
            f"City GIS returned status {exc.response.status_code}.", _GIS_HINT
        ) from None
    except (httpx.RequestError, json.JSONDecodeError, UnicodeDecodeError):
        raise PortalError("City GIS request failed.", _GIS_HINT) from None
    if isinstance(payload, dict) and "error" in payload:
        raise PortalError("City GIS reported an error.", _GIS_HINT)
    return payload


async def _query(layer: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    payload = await _get(f"{layer}/query", {"f": "json", **params})
    return payload.get("features") or []


def _clean(attributes: dict[str, Any]) -> dict[str, Any]:
    """Drop internal ID and geometry-size fields; keep the descriptive ones."""
    return {
        key: value
        for key, value in attributes.items()
        if value not in (None, "")
        and not key.upper().startswith(("SHAPE", "OBJECTID", "FID", "GLOBALID"))
    }


async def _find_address_field() -> str:
    """Read the address layer's field list once and pick the full-address field."""
    global _address_field
    if _address_field:
        return _address_field
    layer = await _get(ADDRESS_LAYER, {"f": "json"})
    strings = [
        f["name"]
        for f in layer.get("fields", [])
        if f.get("type") == "esriFieldTypeString" and f.get("name")
    ]
    by_upper = {name.upper(): name for name in strings}
    for candidate in _ADDRESS_FIELD_NAMES:
        if candidate in by_upper:
            _address_field = by_upper[candidate]
            return _address_field
    for name in strings:
        if "ADDR" in name.upper():
            _address_field = name
            return _address_field
    raise PortalError("The City address layer has no address field.", _GIS_HINT)


async def _containing(layer: str, x: float, y: float) -> list[dict[str, Any]]:
    features = await _query(
        layer,
        {
            "geometry": f"{x},{y}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
        },
    )
    return [_clean(f.get("attributes") or {}) for f in features]


def _is_pending(attributes: dict[str, Any]) -> bool:
    """City limits polygons tagged Pending are under review, not city limits."""
    return any(
        isinstance(v, str) and v.strip().upper() == "PENDING"
        for v in attributes.values()
    )


async def lookup_address(address: str) -> dict[str, Any]:
    """Find a Houston address, then the city limits, council district, and super
    neighborhood that contain it."""
    street = normalize_address(address)
    field = await _find_address_field()
    matches = await _query(
        ADDRESS_LAYER,
        {
            "where": f"UPPER({field}) LIKE '{street}%'",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "resultRecordCount": MAX_MATCHES,
        },
    )
    sources = [
        {"name": s["name"], "url": f"{ARCGIS_ORIGIN}{s['layer']}"} for s in SOURCES
    ]
    if not matches:
        return {
            "found": False,
            "searched_for": street,
            "hint": "Check the spelling and house number. Use the street name "
            "only, without the city or ZIP code.",
            "sources": sources[:1],
        }

    best = matches[0]
    point = best.get("geometry") or {}
    x, y = point.get("x"), point.get("y")
    if x is None or y is None:
        raise PortalError("The matched address has no location.", _GIS_HINT)

    limits, council, neighborhood = await asyncio.gather(
        _containing(CITY_LIMITS_LAYER, x, y),
        _containing(COUNCIL_LAYER, x, y),
        _containing(SUPER_NEIGHBORHOOD_LAYER, x, y),
    )
    inside = any(not _is_pending(a) for a in limits)
    return {
        "found": True,
        "searched_for": street,
        "matched_address": (best.get("attributes") or {}).get(field),
        "address_record": _clean(best.get("attributes") or {}),
        "other_matches": [(m.get("attributes") or {}).get(field) for m in matches[1:]],
        "location": {"longitude": x, "latitude": y},
        "inside_city_limits": inside,
        "city_limits": limits,
        "council_district": council[0] if council and inside else None,
        "super_neighborhood": neighborhood[0] if neighborhood else None,
        "note": (
            "Inside city limits, every resident is also represented by the five "
            "at-large council members and the Mayor."
            if inside
            else "This address is outside Houston city limits, so it has no "
            "City Council district."
        ),
        "sources": sources,
    }
