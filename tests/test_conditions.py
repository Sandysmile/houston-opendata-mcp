"""Weather and air quality by ZIP code, against canned NWS and AirNow responses."""

from __future__ import annotations

import json

import pytest

from houston_opendata import agent, conditions, portal

POINTS = {
    "properties": {
        "gridId": "HGX",
        "gridX": 65,
        "gridY": 97,
        "relativeLocation": {"properties": {"city": "Houston", "state": "TX"}},
    }
}
FORECAST = {
    "properties": {
        "updateTime": "2026-11-13T20:00:00+00:00",
        "periods": [
            {
                "name": f"Period {i}",
                "startTime": "2026-11-13T18:00:00-06:00",
                "temperature": 70 + i,
                "temperatureUnit": "F",
                "probabilityOfPrecipitation": {"value": 20},
                "windSpeed": "5 mph",
                "windDirection": "SE",
                "shortForecast": "Partly Cloudy",
                "detailedForecast": "Partly cloudy.",
            }
            for i in range(14)
        ],
    }
}
ALERTS = {
    "features": [
        {
            "properties": {
                "event": "Flood Watch",
                "severity": "Moderate",
                "headline": "Flood Watch until Saturday",
                "areaDesc": "Harris",
            }
        }
    ]
}
# Shapes of AirNow's 2026 services, which replaced the latLong ones.
AIR_NOW = [
    {
        "dateObserved": "2026-11-13",
        "hourObserved": "19:00",
        "localTimeZone": "CST",
        "reportingAreaName": "Houston",
        "parameterName": "OZONE",
        "nowcastAQI": 42,
        "aqiCategoryName": "Good",
    },
    {
        "dateObserved": "2026-11-13",
        "hourObserved": "19:00",
        "localTimeZone": "CST",
        "reportingAreaName": "Houston",
        "parameterName": "PM2.5",
        "nowcastAQI": 61,
    },
]
AIR_FORECAST = [
    {
        "dateValid": "2026-11-14",
        "reportingAreaName": "Houston",
        "parameterName": "PM2.5",
        "aqi": -1,
        "categoryName": "Moderate",
        "actionDay": False,
        "discussion": "Light winds.",
    }
]


class Calls(list):
    responses: dict


@pytest.fixture
def upstream(monkeypatch):
    calls = Calls()
    responses = {
        "/points/29.7568,-95.3657": POINTS,
        "/gridpoints/HGX/65,97/forecast": FORECAST,
        "/alerts/active": ALERTS,
        conditions.AIR_CURRENT_PATH: AIR_NOW,
        conditions.AIR_FORECAST_PATH: AIR_FORECAST,
    }

    async def fake_get(origin, path, params, service, hint):
        calls.append((origin, path, dict(params)))
        answer = responses[path]
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(conditions, "_get", fake_get)
    monkeypatch.setattr(conditions, "_cache", {})
    monkeypatch.setenv("AIRNOW_API_KEY", "test-key")
    calls.responses = responses
    return calls


def test_zip_list_has_every_city_zip():
    points = conditions.zip_points()
    assert len(points) == 118
    assert points["77002"] == pytest.approx((29.756845, -95.365652))
    for lat, lon in points.values():
        assert 29.4 < lat < 30.2 and -95.9 < lon < -94.9


def test_resolve_zip_inside_outside_and_default():
    assert conditions.resolve_zip("77002-1234")["found"] is True
    outside = conditions.resolve_zip("10001")
    assert outside["found"] is False and "isn't one of" in outside["note"]
    default = conditions.resolve_zip(None)
    assert default["zip"] == conditions.DEFAULT_ZIP and "downtown" in default["note"]
    with pytest.raises(portal.PortalError):
        conditions.resolve_zip("Houston")


async def test_weather_forecast(upstream):
    result = await conditions.weather_forecast("77002", periods=99)

    assert result["near"] == "Houston, TX"
    assert len(result["periods"]) == conditions.MAX_PERIODS
    assert result["periods"][0]["wind"] == "5 mph SE"
    assert result["active_alerts"][0]["event"] == "Flood Watch"
    assert all(origin == conditions.NWS_ORIGIN for origin, _, _ in upstream)
    assert upstream[-1][2] == {"point": "29.7568,-95.3657"}

    # A second question reuses the cached forecast.
    again = await conditions.weather_forecast("77002", periods=2)
    assert len(again["periods"]) == 2
    assert len(upstream) == 3


async def test_weather_rejects_an_odd_forecast_office(upstream, monkeypatch):
    bad = {"properties": {"gridId": "../x", "gridX": 1, "gridY": 2}}

    async def fake_get(origin, path, params, service, hint):
        return bad

    monkeypatch.setattr(conditions, "_get", fake_get)
    with pytest.raises(portal.PortalError):
        await conditions.weather_forecast("77002")


async def test_outside_zip_makes_no_requests(upstream):
    result = await conditions.weather_forecast("75201")
    assert result["found"] is False
    assert upstream == []


async def test_air_quality(upstream):
    result = await conditions.air_quality("77002")

    assert result["reporting_area"] == "Houston"
    assert result["observed"] == "2026-11-13 19:00 CST"
    assert result["current"] == [
        {"pollutant": "OZONE", "aqi": 42, "category": "Good"},
        {"pollutant": "PM2.5", "aqi": 61, "category": "Moderate"},  # from the AQI
    ]
    day = result["forecast"][0]
    assert day["date"] == "2026-11-14"
    assert day["readings"][0] == {
        "pollutant": "PM2.5",
        "aqi": None,  # AirNow uses -1 for no number.
        "category": "Moderate",
    }
    assert day["discussion"] == "Light winds."
    assert "citywide" in result["about_the_data"]
    assert "problems" not in result
    assert {path for _, path, _ in upstream} == {
        conditions.AIR_CURRENT_PATH,
        conditions.AIR_FORECAST_PATH,
    }
    assert all(origin == conditions.AIRNOW_ORIGIN for origin, _, _ in upstream)
    assert upstream[0][2]["API_KEY"] == "test-key"


async def test_air_quality_no_data_envelope(upstream):
    upstream.responses[conditions.AIR_CURRENT_PATH] = {
        "WebServiceError": [{"Message": "No data"}]
    }
    result = await conditions.air_quality("77002")
    assert result["current"] == []
    assert result["reporting_area"] == "Houston"  # from the forecast


async def test_air_quality_keeps_the_half_that_worked(upstream):
    upstream.responses[conditions.AIR_FORECAST_PATH] = portal.PortalError(
        "AirNow returned status 410.", "hint"
    )
    result = await conditions.air_quality("77002")
    assert result["current"][0]["aqi"] == 42
    assert result["forecast"] == []
    assert "410" in result["problems"][0]


async def test_air_quality_fails_when_both_halves_fail(upstream):
    for path in (conditions.AIR_CURRENT_PATH, conditions.AIR_FORECAST_PATH):
        upstream.responses[path] = portal.PortalError(
            "AirNow returned status 401.", "hint"
        )
    with pytest.raises(portal.PortalError) as caught:
        await conditions.air_quality("77002")
    assert "401" in caught.value.error


def test_aqi_categories():
    assert [conditions.aqi_category(n) for n in (0, 50, 51, 151, 301)] == [
        "Good",
        "Good",
        "Moderate",
        "Unhealthy",
        "Hazardous",
    ]
    assert conditions.aqi_category(None) is None


async def test_air_quality_without_a_key(upstream, monkeypatch):
    monkeypatch.delenv("AIRNOW_API_KEY")
    monkeypatch.setattr(conditions.settings, "airnow_api_key", "")
    with pytest.raises(portal.PortalError) as caught:
        await conditions.air_quality("77002")
    assert "AIRNOW_API_KEY" in caught.value.hint
    assert upstream == []


def test_agent_offers_the_tools_only_in_ask_houston_plus():
    plain = {tool["name"] for tool in agent.tools(False)}
    plus = {tool["name"] for tool in agent.tools(True)}
    assert "houston_weather_forecast" not in plain
    assert {"houston_weather_forecast", "houston_air_quality"} <= plus


def test_agent_runs_the_weather_tool(upstream):
    text = agent.run_tool("houston_weather_forecast", {"zip_code": "77002"}, True)
    assert json.loads(text)["near"] == "Houston, TX"
    refused = agent.run_tool("houston_weather_forecast", {"zip_code": "77002"}, False)
    assert "Unknown tool" in json.loads(refused)["error"]
