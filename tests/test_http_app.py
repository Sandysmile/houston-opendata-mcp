"""The HTTP app that hosted deployments run."""

from __future__ import annotations

from starlette.testclient import TestClient

from houston_opendata.app import create_http_app


def test_health_route_responds():
    with TestClient(create_http_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
