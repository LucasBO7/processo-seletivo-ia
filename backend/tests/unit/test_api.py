from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.application.contracts.query_plan import QueryPlan
from app.application.ports.providers import ChatModel, ChatModelError, ChatModelErrorCode
from app.core.config import Settings
from app.core.resources import ApplicationResources
from app.domain.models import RecoverableError, SourceReference
from app.graph.state import AppState
from tests.conftest import StubResources, StubWorkflow
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


@contextmanager
def client_with_workflow(settings: Settings, workflow: StubWorkflow) -> Iterator[TestClient]:
    resources = StubResources(workflow=workflow)

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


def test_search_returns_workflow_plan_candidates_and_sources(settings: Settings) -> None:
    startup_id = uuid4()
    source_id = uuid4()
    workflow = StubWorkflow(
        AppState(
            query_plan=QueryPlan.model_validate_json(plan_response()),
            candidate_startups=[{"startup_id": startup_id, "name": "Startup One", "score": 3.0}],
            selected_sources=[
                SourceReference(
                    source_id=source_id,
                    source_url="https://example.com/source",
                    title="Official source",
                    excerpt="Public evidence",
                )
            ],
            warnings=[],
            errors=[],
            metrics={"query_planner_duration_ms": 1.0, "retriever_duration_ms": 2.0},
        )
    )

    with client_with_workflow(settings, workflow) as client:
        response = client.post(
            "/api/v1/search",
            json={"query": "startups"},
            headers={"X-Correlation-ID": "search-123"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["query_plan"]["status"] == "ready"
    assert body["candidate_startups"][0]["startup_id"] == str(startup_id)
    assert body["selected_sources"][0]["source_id"] == str(source_id)
    assert body["selected_sources"][0]["source_url"] == "https://example.com/source"
    assert workflow.calls[0]["correlation_id"] == "search-123"
    assert workflow.calls[0]["query"] == "startups"


def test_search_reuses_one_workflow_during_application_lifespan(settings: Settings) -> None:
    workflow = StubWorkflow()
    resources = StubResources(workflow=workflow)
    factory_calls = 0

    async def factory(_: Settings) -> ApplicationResources:
        nonlocal factory_calls
        factory_calls += 1
        return cast(ApplicationResources, resources)

    app = create_app(settings, resource_factory=factory)
    with TestClient(app) as client:
        assert client.post("/api/v1/search", json={"query": "first"}).status_code == 200
        assert client.post("/api/v1/search", json={"query": "second"}).status_code == 200

    assert factory_calls == 1
    assert [call["query"] for call in workflow.calls] == ["first", "second"]


def test_search_returns_non_ready_plan_without_results(settings: Settings) -> None:
    workflow = StubWorkflow(
        AppState(
            query_plan=QueryPlan.model_validate_json(
                plan_response(
                    status="needs_clarification",
                    ambiguities=["setor"],
                    clarification_questions=["Qual setor?"],
                )
            ),
            warnings=["query_plan_needs_clarification"],
            errors=[],
        )
    )

    with client_with_workflow(settings, workflow) as client:
        response = client.post("/api/v1/search", json={"query": "startups"})

    assert response.status_code == 200
    assert response.json()["query_plan"]["status"] == "needs_clarification"
    assert response.json()["candidate_startups"] == []


def test_search_returns_invalid_plan_with_http_200(settings: Settings) -> None:
    workflow = StubWorkflow(
        AppState(
            query_plan=QueryPlan.model_validate_json(plan_response(status="invalid")),
            errors=[RecoverableError("query_invalid", "Consulta fora do escopo")],
        )
    )

    with client_with_workflow(settings, workflow) as client:
        response = client.post("/api/v1/search", json={"query": "previsão do tempo"})

    assert response.status_code == 200
    assert response.json()["query_plan"]["status"] == "invalid"
    assert response.json()["errors"][0]["code"] == "query_invalid"


def test_search_treats_empty_retrieval_as_success(settings: Settings) -> None:
    workflow = StubWorkflow(
        AppState(
            query_plan=QueryPlan.model_validate_json(plan_response()),
            candidate_startups=[],
            selected_sources=[],
            warnings=["retriever_no_results"],
            errors=[],
        )
    )

    with client_with_workflow(settings, workflow) as client:
        response = client.post("/api/v1/search", json={"query": "sem resultados"})

    assert response.status_code == 200
    assert response.json()["candidate_startups"] == []
    assert response.json()["selected_sources"] == []
    assert response.json()["warnings"] == ["retriever_no_results"]


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        ("query_empty", 422),
        ("query_too_long", 422),
        ("query_plan_invalid_output", 502),
        ("query_planner_unavailable", 503),
        ("retriever_unavailable", 503),
    ],
)
def test_search_maps_recoverable_errors(
    settings: Settings, code: str, expected_status: int
) -> None:
    workflow = StubWorkflow(
        AppState(errors=[RecoverableError(code=code, message="Safe failure", node="node")])
    )

    with client_with_workflow(settings, workflow) as client:
        response = client.post("/api/v1/search", json={"query": "startups"})

    assert response.status_code == expected_status
    assert response.json()["errors"] == [{"code": code, "message": "Safe failure", "node": "node"}]


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


def test_openapi_exposes_current_functional_routes(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/query-plans" in paths
    assert "/api/v1/search" in paths
    assert "/health/live" not in paths
    assert "/health/ready" not in paths


@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
def test_initial_health_routes_were_removed(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404
