from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.application.contracts.classification import (
    ClassificationStatus,
    ConfidenceLevel,
    StartupClassification,
)
from app.application.contracts.evidence_validation import (
    ClaimValidation,
    EvidenceStatus,
    SourceAssessment,
    SourceVerdict,
    ValidatedStartupProfile,
)
from app.application.contracts.extraction import (
    ExtractionSource,
    ProfileField,
    StructuredStartupProfile,
)
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
    source_pointer = ExtractionSource(
        startup_id=startup_id,
        source_id=source_id,
        source_url="https://example.com/source",
    )
    claim_validation = ClaimValidation(
        startup_id=startup_id,
        claim_key="claims[0]",
        field=ProfileField.CLAIMS,
        value="Public evidence",
        status=EvidenceStatus.SUPPORTED,
        justification="The excerpt supports the claim.",
        original_sources=[source_pointer],
        analyzed_sources=[
            SourceAssessment(
                startup_id=startup_id,
                source_id=source_id,
                source_url="https://example.com/source",
                verdict=SourceVerdict.SUPPORTS,
            )
        ],
    )
    workflow = StubWorkflow(
        AppState(
            query_plan=QueryPlan.model_validate_json(plan_response()),
            candidate_startups=[{"startup_id": startup_id, "name": "Startup One", "score": 3.0}],
            selected_sources=[
                SourceReference(
                    startup_id=startup_id,
                    source_id=source_id,
                    source_url="https://example.com/source",
                    title="Official source",
                    excerpt="Public evidence",
                )
            ],
            structured_profiles=[
                StructuredStartupProfile(
                    startup_id=startup_id,
                    name="Startup One",
                    unknown_fields=[
                        "product",
                        "business_model",
                        "sector",
                        "target_audience",
                        "ai_use_cases",
                        "technologies",
                        "infrastructure",
                        "external_dependencies",
                        "technical_needs",
                        "claims",
                    ],
                )
            ],
            classifications=[
                StartupClassification(
                    startup_id=startup_id,
                    name="Startup One",
                    status=ClassificationStatus.UNCERTAIN,
                    category=None,
                    justification="Insufficient evidence.",
                    confidence=ConfidenceLevel.LOW,
                )
            ],
            validated_profiles=[
                ValidatedStartupProfile(
                    startup_id=startup_id,
                    name="Startup One",
                    unknown_fields=list(ProfileField),
                )
            ],
            claim_validations=[claim_validation],
            validated_claims=[claim_validation],
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
    assert body["outcome"] == "success"
    assert body["query_plan"]["status"] == "ready"
    assert body["candidate_startups"][0]["startup_id"] == str(startup_id)
    assert body["selected_sources"][0]["source_id"] == str(source_id)
    assert body["selected_sources"][0]["startup_id"] == str(startup_id)
    assert body["selected_sources"][0]["source_url"] == "https://example.com/source"
    assert body["structured_profiles"][0]["startup_id"] == str(startup_id)
    assert body["structured_profiles"][0]["name"] == "Startup One"
    assert body["classifications"][0]["status"] == "uncertain"
    assert body["classifications"][0]["category"] is None
    assert body["validated_profiles"][0]["startup_id"] == str(startup_id)
    assert body["claim_validations"][0]["status"] == "supported"
    assert body["claim_validations"][0]["analyzed_sources"][0]["source_url"] == (
        "https://example.com/source"
    )
    assert body["validated_claims"] == body["claim_validations"]
    assert body["rejected_claims"] == []
    assert body["conflicting_claims"] == []
    assert body["evidence_gaps"] == []
    assert body["nvidia_contexts"] == []
    assert body["recommendations"] == []
    assert body["briefings"] == []
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
    assert response.json()["outcome"] == "needs_clarification"
    assert response.json()["query_plan"]["status"] == "needs_clarification"
    assert response.json()["candidate_startups"] == []


def test_search_exposes_unresolved_filter_suggestions(settings: Settings) -> None:
    workflow = StubWorkflow(
        AppState(
            query_plan=QueryPlan.model_validate_json(
                plan_response(
                    status="needs_clarification",
                    filters={},
                    ambiguities=["Setor não reconhecido."],
                    clarification_questions=["Qual categoria representa melhor o setor?"],
                    unresolved_filters=[
                        {"field": "sector", "requested_value": "agricultura espacial"}
                    ],
                    filter_suggestions=[
                        {
                            "field": "sector",
                            "requested_value": "agricultura espacial",
                            "options": [
                                "industry_4_0",
                                "data_and_ai",
                                "managed_it_services",
                            ],
                        }
                    ],
                )
            ),
            warnings=["query_plan_needs_clarification"],
            errors=[],
        )
    )

    with client_with_workflow(settings, workflow) as client:
        response = client.post("/api/v1/search", json={"query": "startups de agricultura espacial"})

    assert response.status_code == 200
    assert response.json()["outcome"] == "needs_clarification"
    plan = response.json()["query_plan"]
    assert plan["unresolved_filters"][0]["requested_value"] == "agricultura espacial"
    assert plan["filter_suggestions"][0]["options"] == [
        "industry_4_0",
        "data_and_ai",
        "managed_it_services",
    ]
    assert response.json()["candidate_startups"] == []


def test_search_returns_invalid_plan_with_http_422(settings: Settings) -> None:
    workflow = StubWorkflow(
        AppState(
            query_plan=QueryPlan.model_validate_json(plan_response(status="invalid")),
            errors=[RecoverableError("query_invalid", "Consulta fora do escopo")],
        )
    )

    with client_with_workflow(settings, workflow) as client:
        response = client.post("/api/v1/search", json={"query": "previsão do tempo"})

    assert response.status_code == 422
    assert response.json()["outcome"] == "invalid_query"
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
    assert response.json()["outcome"] == "no_results"
    assert response.json()["candidate_startups"] == []
    assert response.json()["selected_sources"] == []
    assert response.json()["warnings"] == ["retriever_no_results"]


def test_search_treats_no_supported_claims_as_success(settings: Settings) -> None:
    workflow = StubWorkflow(
        AppState(
            validated_profiles=[],
            validated_claims=[],
            warnings=["validator_no_supported_claims"],
            errors=[],
        )
    )

    with client_with_workflow(settings, workflow) as client:
        response = client.post("/api/v1/search", json={"query": "startups"})

    assert response.status_code == 200
    assert response.json()["validated_claims"] == []
    assert response.json()["warnings"] == ["validator_no_supported_claims"]


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        ("query_empty", 422),
        ("query_too_long", 422),
        ("query_plan_invalid_output", 502),
        ("query_planner_unavailable", 503),
        ("retriever_unavailable", 503),
        ("extractor_invalid_output", 502),
        ("extractor_unavailable", 503),
        ("classifier_invalid_output", 502),
        ("classifier_unavailable", 503),
        ("evidence_validator_invalid_output", 502),
        ("evidence_validator_unavailable", 503),
        ("nvidia_rag_retrieval_unavailable", 503),
        ("recommendation_invalid_output", 502),
        ("recommendation_unavailable", 503),
        ("briefing_invalid_output", 502),
        ("briefing_unavailable", 503),
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
    expected_outcome = {
        422: "invalid_query",
        502: "internal_failure",
        503: "temporarily_unavailable",
    }[expected_status]
    assert response.json()["outcome"] == expected_outcome
    assert response.json()["errors"] == [{"code": code, "message": "Safe failure", "node": "node"}]


def test_search_exposes_only_finite_agent_metrics(settings: Settings) -> None:
    workflow = StubWorkflow(
        AppState(
            metrics={
                "query_planner_duration_ms": 1.0,
                "briefing_items": 2.0,
                "raw_prompt_tokens": 99.0,
                "retriever_invalid": float("inf"),
            }
        )
    )

    with client_with_workflow(settings, workflow) as client:
        response = client.post("/api/v1/search", json={"query": "startups"})

    assert response.json()["metrics"] == {
        "query_planner_duration_ms": 1.0,
        "briefing_items": 2.0,
    }


def test_search_sanitizes_unexpected_workflow_failure(settings: Settings) -> None:
    class FailingWorkflow(StubWorkflow):
        async def ainvoke(self, state: AppState) -> AppState:
            self.calls.append(state.copy())
            raise RuntimeError("password=secret SELECT * FROM private_table traceback")

    workflow = FailingWorkflow()
    with client_with_workflow(settings, workflow) as client:
        response = client.post(
            "/api/v1/search",
            json={"query": "startups"},
            headers={"X-Correlation-ID": "failure-123"},
        )

    assert response.status_code == 500
    assert response.headers["X-Correlation-ID"] == "failure-123"
    assert response.json()["outcome"] == "internal_failure"
    assert response.json()["errors"] == [
        {
            "code": "analysis_internal_error",
            "message": "A análise não pôde ser concluída.",
            "node": None,
        }
    ]
    assert "secret" not in response.text
    assert "SELECT" not in response.text
    assert "traceback" not in response.text


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
    schema = response.json()
    paths = schema["paths"]
    assert "/api/v1/query-plans" in paths
    assert "/api/v1/search" in paths
    assert "/api/v1/analysis" not in paths
    search_schema = schema["components"]["schemas"]["SearchResponse"]
    assert search_schema["properties"]["outcome"]["$ref"].endswith("/AnalysisOutcome")
    assert "recommendations" in search_schema["properties"]
    assert "briefings" in search_schema["properties"]
    assert "/health/live" not in paths
    assert "/health/ready" not in paths
    schemas = response.json()["components"]["schemas"]
    assert "financial_services" in schemas["Sector"]["enum"]
    assert "seed" in schemas["StartupStage"]["enum"]
    assert "small" in schemas["CompanySize"]["enum"]
    assert "FilterSuggestion" in schemas
    assert "StructuredStartupProfile" in schemas
    assert "ExtractedFact" in schemas
    assert "ExtractionSource" in schemas
    assert "ProfileField" in schemas
    assert "StartupClassification" in schemas
    assert "StartupBriefing" in schemas
    assert "ClassificationStatus" in schemas
    assert "ConfidenceLevel" in schemas
    assert "ClassificationSignalType" in schemas
    assert "ValidatedStartupProfile" in schemas
    assert "ValidatedClassification" in schemas
    assert "ClaimValidation" in schemas
    assert "ClassificationValidation" in schemas
    assert "EvidenceStatus" in schemas
    assert "SourceVerdict" in schemas
    assert "NvidiaStartupContext" in schemas
    assert "NvidiaRetrievedChunk" in schemas
    assert "NvidiaContextSufficiency" in schemas
    assert set(schemas["AnalysisOutcome"]["enum"]) == {
        "success",
        "needs_clarification",
        "invalid_query",
        "no_results",
        "temporarily_unavailable",
        "internal_failure",
    }
    operation = paths["/api/v1/search"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/SearchRequest"
    )
    assert "examples" in operation["responses"]["200"]["content"]["application/json"]
    assert "examples" in operation["responses"]["422"]["content"]["application/json"]
    assert "examples" in operation["responses"]["500"]["content"]["application/json"]
    assert "examples" in operation["responses"]["503"]["content"]["application/json"]


@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
def test_initial_health_routes_were_removed(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404
