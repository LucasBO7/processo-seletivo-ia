from __future__ import annotations

from typing import cast

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.application.contracts.query_plan import QueryPlan
from app.core.config import Settings
from app.core.resources import ApplicationResources
from app.graph.builder import compile_analysis_workflow
from app.graph.contracts import AnalysisWorkflow, GraphNode
from app.graph.state import AppState

pytestmark = pytest.mark.integration


def ready_plan() -> QueryPlan:
    return QueryPlan.model_validate(
        {
            "status": "ready",
            "normalized_query": "startups brasileiras",
            "filters": {},
            "analysis_strategy": {
                "mode": "exploratory",
                "objectives": ["encontrar startups"],
                "rationale": "Consulta executável.",
            },
            "ambiguities": [],
            "clarification_questions": [],
        }
    )


def test_analysis_api_invokes_compiled_graph_and_preserves_http_context(
    settings: Settings,
) -> None:
    calls: list[str] = []
    planner_states: list[AppState] = []

    async def query_planner(state: AppState) -> AppState:
        calls.append("query_planner")
        planner_states.append(state.copy())
        return AppState(
            query_plan=ready_plan(),
            metrics={"query_planner_duration_ms": 1.0},
        )

    async def retriever(state: AppState) -> AppState:
        calls.append("retriever")
        return AppState(
            candidate_startups=[],
            selected_sources=[],
            warnings=[*state.get("warnings", []), "retriever_no_results"],
            metrics={**state.get("metrics", {}), "retriever_duration_ms": 2.0},
        )

    async def must_not_run(_: AppState) -> AppState:
        raise AssertionError("a downstream node ran without a startup")

    stop_node = cast(GraphNode, must_not_run)
    workflow = compile_analysis_workflow(
        query_planner=query_planner,
        retriever=retriever,
        extractor=stop_node,
        startup_classifier=stop_node,
        evidence_validator=stop_node,
        nvidia_rag=stop_node,
        recommendation=stop_node,
        briefing=stop_node,
    )

    class ControlledResources:
        def __init__(self, compiled_workflow: AnalysisWorkflow) -> None:
            self.workflow = compiled_workflow
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    resources = ControlledResources(workflow)

    async def factory(_: Settings) -> ApplicationResources:
        return cast(ApplicationResources, resources)

    app = create_app(settings, resource_factory=factory)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/search",
            json={"query": "startups brasileiras"},
            headers={"X-Correlation-ID": "api-graph-123"},
        )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "api-graph-123"
    assert response.json()["outcome"] == "no_results"
    assert response.json()["query_plan"]["status"] == "ready"
    assert response.json()["warnings"] == ["retriever_no_results"]
    assert response.json()["metrics"] == {
        "query_planner_duration_ms": 1.0,
        "retriever_duration_ms": 2.0,
    }
    assert calls == ["query_planner", "retriever"]
    assert planner_states[0]["query"] == "startups brasileiras"
    assert planner_states[0]["correlation_id"] == "api-graph-123"
    assert resources.closed
