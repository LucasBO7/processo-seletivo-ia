from __future__ import annotations

import time
from typing import cast

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.config import Settings
from app.core.resources import ApplicationResources
from tests.conftest import StubResources


def test_liveness_is_fast_and_does_not_call_dependencies(client: TestClient) -> None:
    started_at = time.perf_counter()
    response = client.get("/health/live")
    elapsed = time.perf_counter() - started_at

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert elapsed < 0.2


def test_readiness_reports_dependencies(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"postgres": True, "qdrant": True},
    }


def test_readiness_returns_503_when_dependency_is_unavailable(settings: Settings) -> None:
    resources = StubResources(qdrant_ready=False)

    async def factory(_: Settings) -> ApplicationResources:
        return cast(ApplicationResources, resources)

    app = create_app(settings, resource_factory=factory)
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["dependencies"]["qdrant"] is False


def test_correlation_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Correlation-ID": "request-123"})

    assert response.headers["X-Correlation-ID"] == "request-123"


def test_error_envelope_is_sanitized(client: TestClient) -> None:
    response = client.get("/missing", headers={"X-Correlation-ID": "error-123"})

    assert response.status_code == 404
    assert response.json() == {
        "code": "http_404",
        "message": "Not Found",
        "correlation_id": "error-123",
    }
    assert "traceback" not in response.text.lower()


def test_cors_uses_the_configured_allowlist(client: TestClient) -> None:
    response = client.options(
        "/health/live",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_is_versioned(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    assert "/health/live" in response.json()["paths"]
