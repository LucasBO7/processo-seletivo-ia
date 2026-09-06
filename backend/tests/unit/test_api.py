from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.application.ports.providers import ChatModel, ChatModelError, ChatModelErrorCode
from app.core.config import Settings
from app.core.resources import ApplicationResources
from tests.conftest import StubResources
from tests.fakes.providers import FakeChatModel, SequenceChatModel


def plan_response(**overrides: object) -> str:
    payload: dict[str, object] = {
        "status": "ready",
        "normalized_query": "startups",
        "filters": {},
        "analysis_strategy": {
            "mode": "exploratory",
            "objectives": ["descobrir startups"],
            "rationale": "Consulta ampla e executável.",
        },
        "ambiguities": [],
        "clarification_questions": [],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


@contextmanager
def client_with_model(settings: Settings, model: ChatModel) -> Iterator[TestClient]:
    resources = StubResources(model)

    async def factory(_: Settings) -> ApplicationResources:
        return cast(ApplicationResources, resources)

    app = create_app(settings, resource_factory=factory)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_query_planner_returns_ready_plan(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plans",
        json={"query": "Startups brasileiras de saúde"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_plan"]["status"] == "ready"
    assert body["query_plan"]["normalized_query"] == "Startups brasileiras de saúde"
    assert body["warnings"] == []
    assert body["errors"] == []
    assert "query_planner_duration_ms" in body["metrics"]


@pytest.mark.parametrize(
    ("model_response", "expected_status"),
    [
        (
            plan_response(
                status="needs_clarification",
                ambiguities=["Há dois recortes possíveis."],
                clarification_questions=["Qual recorte você deseja?"],
            ),
            "needs_clarification",
        ),
        (plan_response(status="invalid"), "invalid"),
    ],
)
def test_query_planner_preserves_non_ready_plan_statuses(
    settings: Settings, model_response: str, expected_status: str
) -> None:
    with client_with_model(settings, FakeChatModel(model_response)) as client:
        response = client.post("/api/v1/query-plans", json={"query": "consulta"})

    assert response.status_code == 200
    assert response.json()["query_plan"]["status"] == expected_status


@pytest.mark.parametrize("query", ["", "!!!"])
def test_invalid_query_returns_422(client: TestClient, query: str) -> None:
    response = client.post("/api/v1/query-plans", json={"query": query})

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "query_empty"


def test_invalid_model_output_returns_502(settings: Settings) -> None:
    model = SequenceChatModel(["invalid", "still-invalid"])
    with client_with_model(settings, model) as client:
        response = client.post("/api/v1/query-plans", json={"query": "startups"})

    assert response.status_code == 502
    assert response.json()["errors"][0]["code"] == "query_plan_invalid_output"


def test_unavailable_model_returns_503(settings: Settings) -> None:
    model = SequenceChatModel([ChatModelError(ChatModelErrorCode.UNAVAILABLE, "provider-secret")])
    with client_with_model(settings, model) as client:
        response = client.post("/api/v1/query-plans", json={"query": "startups"})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "query_planner_unavailable"
    assert "provider-secret" not in response.text


def test_request_validation_uses_global_error_envelope(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plans",
        json={},
        headers={"X-Correlation-ID": "validation-123"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "message": "A requisição contém dados inválidos.",
        "correlation_id": "validation-123",
    }


def test_correlation_id_is_propagated(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plans",
        json={"query": "startups"},
        headers={"X-Correlation-ID": "request-123"},
    )

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


def test_cors_allows_post_from_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/query-plans",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_exposes_only_current_functional_route(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/query-plans" in paths
    assert "/health/live" not in paths
    assert "/health/ready" not in paths


@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
def test_initial_health_routes_were_removed(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404
