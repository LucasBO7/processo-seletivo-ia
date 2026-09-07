from __future__ import annotations

import json
from dataclasses import asdict
from uuid import uuid4

import pytest

from app.application.contracts.extraction import ProfileField, StructuredStartupProfile
from app.application.contracts.query_plan import QueryPlan
from app.domain.models import Evidence, RecoverableError, SourceReference
from app.graph.builder import (
    compile_analysis_workflow,
    create_graph_builder,
    route_after_extractor,
    route_after_query_planner,
    route_after_retriever,
)
from app.graph.nodes import ALL_NODE_NAMES, NodeName
from app.graph.state import AppState, CandidateStartup, empty_state


def test_all_eight_node_names_are_centralized() -> None:
    assert len(ALL_NODE_NAMES) == 8
    assert NodeName.QUERY_PLANNER in ALL_NODE_NAMES
    assert NodeName.BRIEFING in ALL_NODE_NAMES


def test_state_accepts_partial_updates_and_traceable_evidence() -> None:
    source = SourceReference(
        startup_id=uuid4(),
        source_id=uuid4(),
        source_url="https://example.com",
        title="Fonte",
    )
    state = empty_state(run_id=uuid4(), correlation_id="corr-1", query="fintechs")
    update = AppState(validated_claims=[Evidence(claim="Usa IA", sources=(source,))])
    state.update(update)

    encoded = json.dumps(
        {**state, "validated_claims": [asdict(item) for item in state["validated_claims"]]},
        default=str,
    )
    assert "https://example.com" in encoded
    assert "corr-1" in encoded


class RecordingNode:
    def __init__(self, update: AppState) -> None:
        self.update = update
        self.calls: list[AppState] = []

    async def __call__(self, state: AppState) -> AppState:
        self.calls.append(state.copy())
        return self.update


def query_plan(status: str = "ready") -> QueryPlan:
    needs_clarification = status == "needs_clarification"
    return QueryPlan.model_validate(
        {
            "status": status,
            "normalized_query": "startups",
            "filters": {},
            "analysis_strategy": {
                "mode": "exploratory",
                "objectives": ["descobrir startups"],
                "rationale": "Consulta executável.",
            },
            "ambiguities": ["setor"] if needs_clarification else [],
            "clarification_questions": ["Qual setor?"] if needs_clarification else [],
        }
    )


def test_builder_registers_current_nodes() -> None:
    builder = create_graph_builder(
        query_planner=RecordingNode(AppState()),
        retriever=RecordingNode(AppState()),
        extractor=RecordingNode(AppState()),
        startup_classifier=RecordingNode(AppState()),
    )

    assert set(builder.nodes) == {
        "query_planner",
        "retriever",
        "extractor",
        "startup_classifier",
    }


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (AppState(query_plan=query_plan()), "retrieve"),
        (AppState(query_plan=query_plan("needs_clarification")), "stop"),
        (AppState(query_plan=query_plan("invalid")), "stop"),
        (AppState(), "stop"),
        (
            AppState(
                query_plan=query_plan(),
                errors=[RecoverableError("query_planner_unavailable", "unavailable")],
            ),
            "stop",
        ),
    ],
)
def test_route_after_query_planner(state: AppState, expected: str) -> None:
    assert route_after_query_planner(state) == expected


def test_route_after_retriever_requires_attributable_source() -> None:
    startup_id = uuid4()
    usable = SourceReference(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/source",
        title="Source",
        excerpt="Evidence",
    )
    candidate = CandidateStartup(startup_id=startup_id, name="Acme", score=1.0)

    assert (
        route_after_retriever(AppState(candidate_startups=[candidate], selected_sources=[usable]))
        == "extract"
    )
    assert (
        route_after_retriever(AppState(candidate_startups=[candidate], selected_sources=[]))
        == "stop"
    )
    assert (
        route_after_retriever(AppState(candidate_startups=[], selected_sources=[usable])) == "stop"
    )


def test_route_after_extractor_requires_profile() -> None:
    profile = StructuredStartupProfile(
        startup_id=uuid4(),
        name="Acme",
        unknown_fields=list(ProfileField),
    )

    assert route_after_extractor(AppState(structured_profiles=[profile])) == "classify"
    assert route_after_extractor(AppState(structured_profiles=[])) == "stop"
    assert route_after_extractor(AppState()) == "stop"


@pytest.mark.asyncio
async def test_workflow_runs_retriever_and_preserves_traceable_state() -> None:
    startup_id = uuid4()
    source = SourceReference(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/evidence",
        title="Evidence",
        excerpt="Traceable evidence",
    )
    planner = RecordingNode(
        AppState(
            query_plan=query_plan(),
            warnings=["planner_warning"],
            metrics={"query_planner_duration_ms": 1.0},
        )
    )
    retriever = RecordingNode(
        AppState(
            candidate_startups=[{"startup_id": startup_id, "name": "Acme", "score": 2.0}],
            selected_sources=[source],
            warnings=["planner_warning"],
            metrics={"query_planner_duration_ms": 1.0, "retriever_duration_ms": 2.0},
        )
    )
    extractor = RecordingNode(AppState())
    startup_classifier = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
    )

    result = await workflow.ainvoke(
        empty_state(run_id=uuid4(), correlation_id="corr-workflow", query="startups")
    )

    assert len(retriever.calls) == 1
    assert len(extractor.calls) == 1
    assert startup_classifier.calls == []
    assert retriever.calls[0]["query_plan"] == query_plan()
    assert result["candidate_startups"][0]["startup_id"] == startup_id
    assert result["selected_sources"][0].source_id == source.source_id
    assert result["selected_sources"][0].source_url == source.source_url
    assert result["warnings"] == ["planner_warning"]
    assert result["metrics"]["retriever_duration_ms"] == 2.0


@pytest.mark.asyncio
async def test_workflow_runs_classifier_only_after_extractor_profile() -> None:
    startup_id = uuid4()
    profile = StructuredStartupProfile(
        startup_id=startup_id,
        name="Acme",
        unknown_fields=list(ProfileField),
    )
    source = SourceReference(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/acme",
        title="Acme",
        excerpt="Evidence",
    )
    planner = RecordingNode(AppState(query_plan=query_plan()))
    retriever = RecordingNode(
        AppState(
            candidate_startups=[{"startup_id": startup_id, "name": "Acme", "score": 1.0}],
            selected_sources=[source],
        )
    )
    extractor = RecordingNode(AppState(structured_profiles=[profile]))
    startup_classifier = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
    )

    await workflow.ainvoke(empty_state(run_id=uuid4(), correlation_id="classify", query="startups"))

    assert len(startup_classifier.calls) == 1
    assert startup_classifier.calls[0]["structured_profiles"] == [profile]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["needs_clarification", "invalid"])
async def test_workflow_stops_before_retriever_for_non_ready_plan(status: str) -> None:
    planner = RecordingNode(AppState(query_plan=query_plan(status)))
    retriever = RecordingNode(AppState())
    extractor = RecordingNode(AppState())
    startup_classifier = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
    )

    result = await workflow.ainvoke(
        empty_state(run_id=uuid4(), correlation_id="corr-stop", query="consulta")
    )

    assert result["query_plan"].status.value == status
    assert retriever.calls == []
    assert extractor.calls == []


@pytest.mark.asyncio
async def test_workflow_stops_before_retriever_when_planner_fails() -> None:
    planner_error = RecoverableError(
        "query_planner_unavailable", "Planner unavailable", "query_planner"
    )
    planner = RecordingNode(AppState(errors=[planner_error]))
    retriever = RecordingNode(AppState())
    extractor = RecordingNode(AppState())
    startup_classifier = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
    )

    result = await workflow.ainvoke(
        empty_state(run_id=uuid4(), correlation_id="corr-error", query="consulta")
    )

    assert result["errors"] == [planner_error]
    assert retriever.calls == []


@pytest.mark.asyncio
async def test_workflow_invocations_do_not_share_mutable_state() -> None:
    planner = RecordingNode(AppState(query_plan=query_plan()))
    retriever = RecordingNode(AppState())
    extractor = RecordingNode(AppState())
    startup_classifier = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
    )

    first = await workflow.ainvoke(
        empty_state(run_id=uuid4(), correlation_id="first", query="first")
    )
    first["warnings"].append("local-change")
    second = await workflow.ainvoke(
        empty_state(run_id=uuid4(), correlation_id="second", query="second")
    )

    assert second["correlation_id"] == "second"
    assert second["warnings"] == []
