"""Weather forecasts (National Weather Service) and air quality (EPA AirNow) by
Houston ZIP code.

Used only by Ask Houston+ (USE_ARCGIS=true). A ZIP code is turned into a point
with data/houston_zip_centroids.csv, which lists the 118 ZIP codes fully or
partially within the City of Houston. Like portal.py and gis.py, both API origins
are fixed here, so tools never accept a URL from the caller. Errors are raised as
PortalError, so the agent and the tools handle them the same way.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from houston_opendata.config import settings
from houston_opendata.portal import PortalError
from houston_opendata.utils import DEFAULT_TIMEOUT, MAX_RESPONSE_BYTES, USER_AGENT

NWS_ORIGIN = "https://api.weather.gov"
AIRNOW_ORIGIN = "https://www.airnowapi.org"

ZIP_FILE = Path(__file__).resolve().parent / "data" / "houston_zip_centroids.csv"
DEFAULT_ZIP = "77002"  # Downtown, used when a question names no ZIP code.

FORECAST_TTL = 30 * 60  # NWS updates forecasts a few times a day.
AIR_TTL = 30 * 60  # AirNow updates observations hourly, forecasts daily.
GRID_TTL = 7 * 24 * 60 * 60  # A ZIP's forecast grid square rarely changes.
SEARCH_MILES = 25  # Finds a Houston air quality reporting area from any ZIP.
MAX_PERIODS = 14  # Seven days of day and night periods.

WEATHER_SOURCE = {
    "name": "National Weather Service (api.weather.gov)",
    "url": "https://www.weather.gov/documentation/services-web-api",
}
AIR_SOURCE = {"name": "EPA AirNow", "url": "https://www.airnow.gov"}
ZIP_SOURCE = (
    "ZIP list: City of Houston Open Data Portal. Center points: U.S. Census "
    "Bureau 2026 ZCTA Gazetteer."
)

_ZIP_HINT = "Give a 5-digit ZIP code, such as 77002."
_NWS_HINT = "The National Weather Service may be busy. Try again shortly."
_AIR_HINT = "AirNow may be busy. Try again shortly."
_KEY_HINT = (
    "Add AIRNOW_API_KEY to the app's secrets. A free key comes from "
    "https://docs.airnowapi.org."
)
_GRID_ID = re.compile(r"^[A-Z]{3}$")

_cache: dict[str, tuple[float, Any]] = {}


@lru_cache(maxsize=1)
def zip_points() -> dict[str, tuple[float, float]]:
    """ZIP code → (latitude, longitude) for every ZIP code in the City."""
    with ZIP_FILE.open(newline="", encoding="utf-8") as handle:
        return {
            row["zip"]: (float(row["lat"]), float(row["lon"]))
            for row in csv.DictReader(handle)
        }


def _remembered(key: str) -> Any:
    hit = _cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    return None


def _remember(key: str, value: Any, ttl: float) -> Any:
    _cache[key] = (time.monotonic() + ttl, value)
    return value


def resolve_zip(zip_code: str | None) -> dict[str, Any]:
    """Check a ZIP code against the City list and return its point.

    Returns `{"found": False, ...}` for a well-formed ZIP code outside the City.
    Raises PortalError for input that isn't a ZIP code.
    """
    if not zip_code or not str(zip_code).strip():
        zip_code, defaulted = DEFAULT_ZIP, True
    else:
        defaulted = False
    value = str(zip_code).strip()[:5]
    if not (len(value) == 5 and value.isdigit()):
        raise PortalError("That isn't a ZIP code.", _ZIP_HINT)
    point = zip_points().get(value)
    if point is None:
        return {
            "found": False,
            "zip": value,
            "note": f"{value} isn't one of the ZIP codes fully or partially within "
            "the City of Houston, so this tool doesn't cover it.",
            "zip_source": ZIP_SOURCE,
        }
    result = {"found": True, "zip": value, "latitude": point[0], "longitude": point[1]}
    if defaulted:
        result["note"] = (
            f"No ZIP code was given, so this uses {DEFAULT_ZIP} (downtown Houston)."
        )
    return result


async def _get(
    origin: str, path: str, params: dict[str, Any], service: str, hint: str
) -> Any:
    """GET one path from a fixed origin and return parsed JSON.

    Error messages never include the request URL, which can carry an API key.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json, */*"}
    try:
        async with httpx.AsyncClient(
            base_url=origin,
            follow_redirects=False,
            timeout=DEFAULT_TIMEOUT,
            trust_env=False,
            headers=headers,
        ) as client:
            async with client.stream("GET", path, params=params) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise PortalError(f"{service} response was too large.", hint)
                return json.loads(content)
    except PortalError:
        raise
    except httpx.HTTPStatusError as exc:
        raise PortalError(
            f"{service} returned status {exc.response.status_code}.", hint
        ) from None
    except (httpx.RequestError, json.JSONDecodeError, UnicodeDecodeError):
        raise PortalError(f"{service} request failed.", hint) from None


# ── Weather ──────────────────────────────────────────────────────────────────


async def _nws(path: str, params: dict[str, Any] | None = None) -> Any:
    return await _get(NWS_ORIGIN, path, params or {}, "The weather service", _NWS_HINT)


async def _grid(zip_code: str, lat: float, lon: float) -> dict[str, Any]:
    """Find the NWS forecast office and 2.5 km grid square for a ZIP code."""
    key = f"grid:{zip_code}"
    cached = _remembered(key)
    if cached:
        return cached
    payload = await _nws(f"/points/{lat:.4f},{lon:.4f}")
    props = payload.get("properties") or {}
    office, x, y = props.get("gridId"), props.get("gridX"), props.get("gridY")
    # Build the forecast path ourselves instead of following a returned URL.
    if not (
        isinstance(office, str)
        and _GRID_ID.match(office)
        and isinstance(x, int)
        and isinstance(y, int)
    ):
        raise PortalError("The weather service returned no forecast area.", _NWS_HINT)
    place = (props.get("relativeLocation") or {}).get("properties") or {}
    grid = {
        "office": office,
        "x": x,
        "y": y,
        "near": ", ".join(p for p in (place.get("city"), place.get("state")) if p),
    }
    return _remember(key, grid, GRID_TTL)


def _period(p: dict[str, Any]) -> dict[str, Any]:
    rain = (p.get("probabilityOfPrecipitation") or {}).get("value")
    return {
        "name": p.get("name"),
        "start": p.get("startTime"),
        "temperature": p.get("temperature"),
        "temperature_unit": p.get("temperatureUnit"),
        "chance_of_rain_percent": rain,
        "wind": " ".join(
            w for w in (p.get("windSpeed"), p.get("windDirection")) if w
        ).strip(),
        "summary": p.get("shortForecast"),
        "details": p.get("detailedForecast"),
    }


def _alert(feature: dict[str, Any]) -> dict[str, Any]:
    a = feature.get("properties") or {}
    return {
        "event": a.get("event"),
        "severity": a.get("severity"),
        "headline": a.get("headline"),
        "areas": a.get("areaDesc"),
        "starts": a.get("onset") or a.get("effective"),
        "ends": a.get("ends") or a.get("expires"),
        "instruction": a.get("instruction"),
    }


async def weather_forecast(zip_code: str | None = None, periods: int = 6) -> dict:
    """The NWS forecast and any active weather alerts for a Houston ZIP code."""
    place = resolve_zip(zip_code)
    if not place["found"]:
        return place
    periods = max(1, min(int(periods or 6), MAX_PERIODS))
    zip_value, lat, lon = place["zip"], place["latitude"], place["longitude"]

    key = f"weather:{zip_value}"
    cached = _remembered(key)
    if not cached:
        grid = await _grid(zip_value, lat, lon)
        forecast, alerts = await asyncio.gather(
            _nws(f"/gridpoints/{grid['office']}/{grid['x']},{grid['y']}/forecast"),
            _nws("/alerts/active", {"point": f"{lat:.4f},{lon:.4f}"}),
        )
        props = forecast.get("properties") or {}
        cached = _remember(
            key,
            {
                "near": grid["near"],
                "updated": props.get("updateTime") or props.get("updated"),
                "periods": [_period(p) for p in props.get("periods") or []],
                "alerts": [_alert(f) for f in alerts.get("features") or []],
            },
            FORECAST_TTL,
        )

    result = {**place, **cached, "periods": cached["periods"][:periods]}
    result["active_alerts"] = result.pop("alerts")
    result["sources"] = [WEATHER_SOURCE]
    result["zip_source"] = ZIP_SOURCE
    return result


# ── Air quality ──────────────────────────────────────────────────────────────


def airnow_key() -> str:
    """The AirNow key from the environment or settings, read at call time so a
    key added to Streamlit secrets after startup is still found."""
    return os.environ.get("AIRNOW_API_KEY", "").strip() or settings.airnow_api_key


# AirNow retired its latLong and zipCode services on September 30, 2026. These
# are the replacements announced in June 2026. Their field names are camelCase
# (nowcastAQI, aqiCategoryName, reportingAreaName), and an area with no data
# answers 200 with a {"WebServiceError": [...]} envelope instead of [].
AIR_CURRENT_PATH = "/aq/observation/current/ziplatlong/"
AIR_FORECAST_PATH = "/aq/forecast/current/"

# EPA AQI category upper bounds, used when a response gives a number but no name.
_AQI_CATEGORIES = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for Sensitive Groups"),
    (200, "Unhealthy"),
    (300, "Very Unhealthy"),
]


def _pick(row: dict[str, Any], *names: str) -> Any:
    """The first non-empty value among several spellings of a field."""
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value.strip() if isinstance(value, str) else value
    return None


def _aqi(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None  # AirNow uses -1 for "no number".


def aqi_category(aqi: int | None) -> str | None:
    if aqi is None:
        return None
    for upper, name in _AQI_CATEGORIES:
        if aqi <= upper:
            return name
    return "Hazardous"


def _category(row: dict[str, Any], aqi: int | None) -> str | None:
    name = _pick(row, "aqiCategoryName", "categoryName", "category")
    if isinstance(name, dict):
        name = name.get("Name") or name.get("name")
    if not name:
        name = (row.get("Category") or {}).get("Name")
    return name or aqi_category(aqi)


def _rows(payload: Any) -> list[dict[str, Any]]:
    """AirNow rows, treating the no-data envelope as an empty list."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and "WebServiceError" in payload:
        return []
    raise PortalError("AirNow returned an unexpected response.", _AIR_HINT)


def _current_reading(r: dict[str, Any]) -> dict[str, Any]:
    aqi = _aqi(_pick(r, "nowcastAQI", "aqi", "AQI"))
    return {
        "pollutant": _pick(r, "parameterName", "ParameterName"),
        "aqi": aqi,
        "category": _category(r, aqi),
    }


def _forecast_reading(r: dict[str, Any]) -> dict[str, Any]:
    aqi = _aqi(_pick(r, "aqi", "forecastAQI", "AQI"))
    return {
        "pollutant": _pick(r, "parameterName", "ParameterName"),
        "aqi": aqi,
        "category": _category(r, aqi),
    }


def _observed(row: dict[str, Any]) -> str | None:
    if not row:
        return None
    date = _pick(row, "dateObserved", "DateObserved", "validDate")
    hour = _pick(row, "hourObserved", "HourObserved", "timeObserved")
    if isinstance(hour, int):
        hour = f"{hour}:00"
    zone = _pick(row, "localTimeZone", "timeZone", "LocalTimeZone")
    text = " ".join(str(v) for v in (date, hour, zone) if v)
    return text or None


def _forecast_days(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    days: dict[str, dict[str, Any]] = {}
    for r in rows:
        date = str(
            _pick(r, "dateValid", "dateForecast", "forecastDate", "DateForecast") or ""
        ).strip()
        day = days.setdefault(
            date,
            {"date": date, "readings": [], "action_day": False, "discussion": None},
        )
        day["readings"].append(_forecast_reading(r))
        action = _pick(r, "actionDay", "ActionDay")
        day["action_day"] = day["action_day"] or action in (True, "true", "True", 1)
        day["discussion"] = day["discussion"] or _pick(r, "discussion", "Discussion")
    return list(days.values())


async def air_quality(zip_code: str | None = None) -> dict:
    """Current air quality and the AirNow forecast for a Houston ZIP code.

    The current reading and the forecast are separate requests. If only one of
    them fails, the other is still returned, with a note about the gap.
    """
    place = resolve_zip(zip_code)
    if not place["found"]:
        return place
    api_key = airnow_key()
    if not api_key:
        raise PortalError("Air quality isn't set up yet.", _KEY_HINT)
    zip_value, lat, lon = place["zip"], place["latitude"], place["longitude"]

    key = f"air:{zip_value}"
    cached = _remembered(key)
    if not cached:
        params = {
            "format": "application/json",
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "distance": SEARCH_MILES,
            "API_KEY": api_key,
        }
        current, forecast = await asyncio.gather(
            _get(AIRNOW_ORIGIN, AIR_CURRENT_PATH, params, "AirNow", _AIR_HINT),
            _get(AIRNOW_ORIGIN, AIR_FORECAST_PATH, params, "AirNow", _AIR_HINT),
            return_exceptions=True,
        )
        problems: list[str] = []
        parts: list[list[dict[str, Any]]] = []
        for label, payload in (("current reading", current), ("forecast", forecast)):
            if isinstance(payload, BaseException):
                if not isinstance(payload, PortalError):
                    raise payload
                problems.append(f"The AirNow {label} wasn't available: {payload.error}")
                parts.append([])
                continue
            try:
                parts.append(_rows(payload))
            except PortalError as exc:
                problems.append(f"The AirNow {label} wasn't available: {exc.error}")
                parts.append([])
        if len(problems) == 2:
            raise PortalError(
                "AirNow couldn't be reached. " + " ".join(problems), _AIR_HINT
            )
        current_rows, forecast_rows = parts

        first = current_rows[0] if current_rows else {}
        area = _pick(first, "reportingAreaName", "reportingArea", "ReportingArea")
        if not area and forecast_rows:
            area = _pick(
                forecast_rows[0], "reportingAreaName", "reportingArea", "ReportingArea"
            )
        value = {
            "reporting_area": area,
            "observed": _observed(first),
            "current": [_current_reading(r) for r in current_rows],
            "forecast": _forecast_days(forecast_rows),
            "problems": problems,
        }
        # Don't keep a partial answer for long; try again on the next question.
        cached = _remember(key, value, 120 if problems else AIR_TTL)

    note = (
        "AirNow reports air quality by reporting area, not by ZIP code. Most "
        "Houston ZIP codes share one reporting area, so treat this as a citywide "
        "reading rather than a neighborhood one."
    )
    if not cached["current"] and not cached["forecast"]:
        note = "AirNow has no current reading or forecast near this ZIP code."
    result = {**place, **cached, "about_the_data": note}
    if not result["problems"]:
        result.pop("problems")
    result["sources"] = [AIR_SOURCE]
    result["zip_source"] = ZIP_SOURCE
    return result
