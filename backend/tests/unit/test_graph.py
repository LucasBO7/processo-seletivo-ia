from __future__ import annotations

import json
from dataclasses import asdict
from uuid import UUID, uuid4

import pytest

from app.application.contracts.evidence_validation import ValidatedStartupProfile
from app.application.contracts.extraction import (
    ExtractedFact,
    ExtractionSource,
    ProfileField,
    StructuredStartupProfile,
)
from app.application.contracts.knowledge_ingestion import NvidiaTechnology
from app.application.contracts.nvidia_rag import (
    NvidiaContextStatus,
    NvidiaContextSufficiency,
    NvidiaQueryTrace,
    NvidiaRankingMode,
    NvidiaRetrievalScores,
    NvidiaRetrievedChunk,
    NvidiaStartupContext,
)
from app.application.contracts.query_plan import QueryPlan
from app.application.contracts.recommendation import StartupRecommendation
from app.domain.models import RecoverableError, SourceReference
from app.graph.builder import (
    compile_analysis_workflow,
    create_graph_builder,
    route_after_classifier,
    route_after_evidence_validator,
    route_after_extractor,
    route_after_nvidia_rag,
    route_after_query_planner,
    route_after_recommendation,
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
    update = AppState(selected_sources=[source])
    state.update(update)

    encoded = json.dumps(
        {**state, "selected_sources": [asdict(item) for item in state["selected_sources"]]},
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
        evidence_validator=RecordingNode(AppState()),
        nvidia_rag=RecordingNode(AppState()),
        recommendation=RecordingNode(AppState()),
        briefing=RecordingNode(AppState()),
    )

    assert set(builder.nodes) == {
        "query_planner",
        "retriever",
        "extractor",
        "startup_classifier",
        "evidence_validator",
        "nvidia_rag",
        "recommendation",
        "briefing",
    }


def test_route_after_nvidia_rag_requires_matching_sufficient_citable_context() -> None:
    profile, source_ids = _usable_profile_for_recommendation()
    context = _sufficient_context_for_recommendation(profile.startup_id)
    assert (
        route_after_nvidia_rag(AppState(validated_profiles=[profile], nvidia_contexts=[context]))
        == "recommend"
    )
    assert route_after_nvidia_rag(AppState(validated_profiles=[profile])) == "stop"
    assert source_ids


def test_route_after_recommendation_requires_a_valid_recommendation() -> None:
    recommendation = StartupRecommendation.model_construct(startup_id=uuid4())

    assert route_after_recommendation(AppState(recommendations=[recommendation])) == "brief"
    assert route_after_recommendation(AppState(recommendations=[])) == "stop"
    assert route_after_recommendation(AppState(recommendations=[{"invalid": True}])) == "stop"


def _usable_profile_for_recommendation() -> tuple[ValidatedStartupProfile, list[UUID]]:
    startup_id = uuid4()
    source = ExtractionSource(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/evidence",
    )
    return (
        ValidatedStartupProfile(
            startup_id=startup_id,
            name="Acme",
            technical_needs=[ExtractedFact(value="Inference API", sources=[source])],
            unknown_fields=[
                field for field in ProfileField if field is not ProfileField.TECHNICAL_NEEDS
            ],
        ),
        [source.source_id],
    )


def _sufficient_context_for_recommendation(startup_id: UUID) -> NvidiaStartupContext:
    chunk = NvidiaRetrievedChunk(
        startup_id=startup_id,
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="NIM API",
        title="NIM",
        technology=NvidiaTechnology.NVIDIA_NIM,
        source_key="nim",
        source_url="https://www.nvidia.com/nim",
        chunk_index=0,
        source_section="API",
        retrieval_attempts=[1],
        matched_queries=["inference"],
        scores=NvidiaRetrievalScores(
            vector_weight=0.5,
            lexical_weight=0.5,
            hybrid_score=0.8,
        ),
    )
    return NvidiaStartupContext(
        startup_id=startup_id,
        startup_name="Acme",
        attempted_queries=["inference"],
        query_traces=[NvidiaQueryTrace(attempt=1, text="inference")],
        attempts=1,
        chunks=[chunk],
        sufficiency=NvidiaContextSufficiency(
            status=NvidiaContextStatus.SUFFICIENT,
            relevant_chunk_count=1,
            distinct_document_count=1,
            best_score=0.8,
            threshold=0.2,
            ranking_mode=NvidiaRankingMode.HYBRID_FALLBACK,
        ),
    )


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


def test_route_after_classifier_requires_profile_not_classification() -> None:
    profile = StructuredStartupProfile(
        startup_id=uuid4(), name="Acme", unknown_fields=list(ProfileField)
    )

    assert route_after_classifier(AppState(structured_profiles=[profile])) == "validate"
    assert route_after_classifier(AppState(structured_profiles=[])) == "stop"


def test_route_after_validator_requires_usable_validated_profile() -> None:
    startup_id = uuid4()
    source = ExtractionSource(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/evidence",
    )
    usable = ValidatedStartupProfile(
        startup_id=startup_id,
        name="Acme",
        product=ExtractedFact(value="AI product", sources=[source]),
        unknown_fields=[field for field in ProfileField if field is not ProfileField.PRODUCT],
    )
    empty = ValidatedStartupProfile(
        startup_id=uuid4(), name="Empty", unknown_fields=list(ProfileField)
    )

    assert route_after_evidence_validator(AppState(validated_profiles=[usable])) == (
        "retrieve_nvidia"
    )
    assert route_after_evidence_validator(AppState(validated_profiles=[empty])) == "stop"
    assert route_after_evidence_validator(AppState()) == "stop"


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
    evidence_validator = RecordingNode(AppState())
    nvidia_rag = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
        evidence_validator=evidence_validator,
        nvidia_rag=nvidia_rag,
        recommendation=RecordingNode(AppState()),
        briefing=RecordingNode(AppState()),
    )

    result = await workflow.ainvoke(
        empty_state(run_id=uuid4(), correlation_id="corr-workflow", query="startups")
    )

    assert len(retriever.calls) == 1
    assert len(extractor.calls) == 1
    assert startup_classifier.calls == []
    assert evidence_validator.calls == []
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
    evidence_validator = RecordingNode(AppState())
    nvidia_rag = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
        evidence_validator=evidence_validator,
        nvidia_rag=nvidia_rag,
        recommendation=RecordingNode(AppState()),
        briefing=RecordingNode(AppState()),
    )

    await workflow.ainvoke(empty_state(run_id=uuid4(), correlation_id="classify", query="startups"))

    assert len(startup_classifier.calls) == 1
    assert startup_classifier.calls[0]["structured_profiles"] == [profile]
    assert len(evidence_validator.calls) == 1
    assert evidence_validator.calls[0]["structured_profiles"] == [profile]


@pytest.mark.asyncio
async def test_workflow_runs_nvidia_rag_only_after_usable_validated_profile() -> None:
    startup_id = uuid4()
    source_id = uuid4()
    pointer = ExtractionSource(
        startup_id=startup_id,
        source_id=source_id,
        source_url="https://example.com/evidence",
    )
    profile = ValidatedStartupProfile(
        startup_id=startup_id,
        name="Acme",
        product=ExtractedFact(value="AI product", sources=[pointer]),
        unknown_fields=[field for field in ProfileField if field is not ProfileField.PRODUCT],
    )
    source = SourceReference(
        startup_id=startup_id,
        source_id=source_id,
        source_url=pointer.source_url,
        title="Acme",
        excerpt="AI product",
    )
    nvidia_rag = RecordingNode(AppState(nvidia_contexts=[]))
    workflow = compile_analysis_workflow(
        query_planner=RecordingNode(AppState(query_plan=query_plan())),
        retriever=RecordingNode(
            AppState(
                candidate_startups=[{"startup_id": startup_id, "name": "Acme", "score": 1.0}],
                selected_sources=[source],
            )
        ),
        extractor=RecordingNode(AppState(structured_profiles=[profile])),
        startup_classifier=RecordingNode(AppState()),
        evidence_validator=RecordingNode(AppState(validated_profiles=[profile])),
        nvidia_rag=nvidia_rag,
        recommendation=RecordingNode(AppState()),
        briefing=RecordingNode(AppState()),
    )

    await workflow.ainvoke(empty_state(run_id=uuid4(), correlation_id="nvidia", query="startups"))

    assert len(nvidia_rag.calls) == 1
    assert nvidia_rag.calls[0]["validated_profiles"] == [profile]


@pytest.mark.asyncio
async def test_workflow_runs_recommendation_after_sufficient_nvidia_context() -> None:
    profile, source_ids = _usable_profile_for_recommendation()
    context = _sufficient_context_for_recommendation(profile.startup_id)
    source = SourceReference(
        startup_id=profile.startup_id,
        source_id=source_ids[0],
        source_url="https://example.com/evidence",
        title="Evidence",
        excerpt="Inference API",
    )
    generated_recommendation = StartupRecommendation.model_construct(startup_id=profile.startup_id)
    recommendation = RecordingNode(AppState(recommendations=[generated_recommendation]))
    briefing = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=RecordingNode(AppState(query_plan=query_plan())),
        retriever=RecordingNode(
            AppState(
                candidate_startups=[
                    {"startup_id": profile.startup_id, "name": profile.name, "score": 1.0}
                ],
                selected_sources=[source],
            )
        ),
        extractor=RecordingNode(AppState(structured_profiles=[profile])),
        startup_classifier=RecordingNode(AppState()),
        evidence_validator=RecordingNode(AppState(validated_profiles=[profile])),
        nvidia_rag=RecordingNode(AppState(nvidia_contexts=[context])),
        recommendation=recommendation,
        briefing=briefing,
    )

    await workflow.ainvoke(
        empty_state(run_id=uuid4(), correlation_id="recommend", query="startups")
    )

    assert len(recommendation.calls) == 1
    assert recommendation.calls[0]["nvidia_contexts"] == [context]
    assert len(briefing.calls) == 1
    assert briefing.calls[0]["recommendations"] == [generated_recommendation]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["needs_clarification", "invalid"])
async def test_workflow_stops_before_retriever_for_non_ready_plan(status: str) -> None:
    planner = RecordingNode(AppState(query_plan=query_plan(status)))
    retriever = RecordingNode(AppState())
    extractor = RecordingNode(AppState())
    startup_classifier = RecordingNode(AppState())
    evidence_validator = RecordingNode(AppState())
    nvidia_rag = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
        evidence_validator=evidence_validator,
        nvidia_rag=nvidia_rag,
        recommendation=RecordingNode(AppState()),
        briefing=RecordingNode(AppState()),
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
    evidence_validator = RecordingNode(AppState())
    nvidia_rag = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
        evidence_validator=evidence_validator,
        nvidia_rag=nvidia_rag,
        recommendation=RecordingNode(AppState()),
        briefing=RecordingNode(AppState()),
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
    evidence_validator = RecordingNode(AppState())
    nvidia_rag = RecordingNode(AppState())
    workflow = compile_analysis_workflow(
        query_planner=planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
        evidence_validator=evidence_validator,
        nvidia_rag=nvidia_rag,
        recommendation=RecordingNode(AppState()),
        briefing=RecordingNode(AppState()),
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
