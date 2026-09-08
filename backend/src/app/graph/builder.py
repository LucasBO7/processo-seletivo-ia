from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.application.contracts.evidence_validation import ValidatedStartupProfile
from app.application.contracts.extraction import StructuredStartupProfile
from app.application.contracts.nvidia_rag import NvidiaContextStatus, NvidiaStartupContext
from app.application.contracts.query_plan import QueryPlan, QueryPlanStatus
from app.application.contracts.recommendation import StartupRecommendation
from app.domain.models import SourceReference
from app.graph.contracts import AnalysisWorkflow, GraphNode
from app.graph.nodes import NodeName
from app.graph.state import AppState

RouteAfterPlanner = Literal["retrieve", "stop"]
RouteAfterRetriever = Literal["extract", "stop"]
RouteAfterExtractor = Literal["classify", "stop"]
RouteAfterClassifier = Literal["validate", "stop"]
RouteAfterEvidenceValidator = Literal["retrieve_nvidia", "stop"]
RouteAfterNvidiaRag = Literal["recommend", "stop"]
RouteAfterRecommendation = Literal["brief", "stop"]
BLOCKING_PLANNER_ERRORS = {
    "query_empty",
    "query_too_long",
    "query_invalid",
    "query_plan_invalid_output",
    "query_planner_unavailable",
}
PIPELINE_NODE_ORDER: tuple[NodeName, ...] = (
    NodeName.QUERY_PLANNER,
    NodeName.RETRIEVER,
    NodeName.EXTRACTOR,
    NodeName.STARTUP_CLASSIFIER,
    NodeName.EVIDENCE_VALIDATOR,
    NodeName.NVIDIA_RAG,
    NodeName.RECOMMENDATION,
    NodeName.BRIEFING,
)


def _candidate_startup_id(value: object) -> UUID | None:
    if not isinstance(value, dict):
        return None
    startup_id = value.get("startup_id")
    name = value.get("name")
    if not isinstance(startup_id, UUID) or not isinstance(name, str) or not name.strip():
        return None
    return startup_id


def route_after_query_planner(state: AppState) -> RouteAfterPlanner:
    """Route only executable, error-free plans to the Retriever."""
    plan = state.get("query_plan")
    has_blocking_error = any(
        error.code in BLOCKING_PLANNER_ERRORS for error in state.get("errors", [])
    )
    if (
        isinstance(plan, QueryPlan)
        and plan.status is QueryPlanStatus.READY
        and not has_blocking_error
    ):
        return "retrieve"
    return "stop"


def route_after_retriever(state: AppState) -> RouteAfterRetriever:
    """Extract only when a candidate has an attributable, usable source."""
    candidate_ids = {
        startup_id
        for candidate in state.get("candidate_startups", [])
        if (startup_id := _candidate_startup_id(candidate)) is not None
    }
    has_appropriate_source = any(
        isinstance(source, SourceReference)
        and source.startup_id in candidate_ids
        and source.source_url.strip()
        and source.excerpt is not None
        and source.excerpt.strip()
        for source in state.get("selected_sources", [])
    )
    return "extract" if candidate_ids and has_appropriate_source else "stop"


def route_after_extractor(state: AppState) -> RouteAfterExtractor:
    """Classify only when the Extractor produced a validated profile."""
    return (
        "classify"
        if any(
            isinstance(profile, StructuredStartupProfile)
            for profile in state.get("structured_profiles", [])
        )
        else "stop"
    )


def route_after_classifier(state: AppState) -> RouteAfterClassifier:
    """Validate evidence whenever at least one structured profile exists."""
    return (
        "validate"
        if any(
            isinstance(profile, StructuredStartupProfile)
            for profile in state.get("structured_profiles", [])
        )
        else "stop"
    )


def route_after_evidence_validator(state: AppState) -> RouteAfterEvidenceValidator:
    """Retrieve NVIDIA context only for profiles containing validated facts."""
    from app.graph.agents.nvidia_rag import is_usable_profile

    return (
        "retrieve_nvidia"
        if any(
            isinstance(profile, ValidatedStartupProfile) and is_usable_profile(profile)
            for profile in state.get("validated_profiles", [])
        )
        else "stop"
    )


def route_after_nvidia_rag(state: AppState) -> RouteAfterNvidiaRag:
    """Recommend only for matching usable profiles and sufficient citable contexts."""
    from app.graph.agents.nvidia_rag import is_usable_profile

    usable_ids = {
        profile.startup_id
        for profile in state.get("validated_profiles", [])
        if is_usable_profile(profile)
    }
    eligible = any(
        isinstance(context, NvidiaStartupContext)
        and context.startup_id in usable_ids
        and context.sufficiency.status is NvidiaContextStatus.SUFFICIENT
        and any(chunk.startup_id == context.startup_id for chunk in context.chunks)
        for context in state.get("nvidia_contexts", [])
    )
    return "recommend" if eligible else "stop"


def route_after_recommendation(state: AppState) -> RouteAfterRecommendation:
    """Build briefings only when at least one validated recommendation exists."""
    return (
        "brief"
        if any(isinstance(item, StartupRecommendation) for item in state.get("recommendations", []))
        else "stop"
    )


def create_graph_builder(
    *,
    query_planner: GraphNode,
    retriever: GraphNode,
    extractor: GraphNode,
    startup_classifier: GraphNode,
    evidence_validator: GraphNode,
    nvidia_rag: GraphNode,
    recommendation: GraphNode,
    briefing: GraphNode,
) -> StateGraph[AppState, None, AppState, AppState]:
    builder = StateGraph(AppState)
    builder.add_node(NodeName.QUERY_PLANNER.value, query_planner)
    builder.add_node(NodeName.RETRIEVER.value, retriever)
    builder.add_node(NodeName.EXTRACTOR.value, extractor)
    builder.add_node(NodeName.STARTUP_CLASSIFIER.value, startup_classifier)
    builder.add_node(NodeName.EVIDENCE_VALIDATOR.value, evidence_validator)
    builder.add_node(NodeName.NVIDIA_RAG.value, nvidia_rag)
    builder.add_node(NodeName.RECOMMENDATION.value, recommendation)
    builder.add_node(NodeName.BRIEFING.value, briefing)
    builder.add_edge(START, NodeName.QUERY_PLANNER.value)
    builder.add_conditional_edges(
        NodeName.QUERY_PLANNER.value,
        route_after_query_planner,
        {"retrieve": NodeName.RETRIEVER.value, "stop": END},
    )
    builder.add_conditional_edges(
        NodeName.RETRIEVER.value,
        route_after_retriever,
        {"extract": NodeName.EXTRACTOR.value, "stop": END},
    )
    builder.add_conditional_edges(
        NodeName.EXTRACTOR.value,
        route_after_extractor,
        {"classify": NodeName.STARTUP_CLASSIFIER.value, "stop": END},
    )
    builder.add_conditional_edges(
        NodeName.STARTUP_CLASSIFIER.value,
        route_after_classifier,
        {"validate": NodeName.EVIDENCE_VALIDATOR.value, "stop": END},
    )
    builder.add_conditional_edges(
        NodeName.EVIDENCE_VALIDATOR.value,
        route_after_evidence_validator,
        {"retrieve_nvidia": NodeName.NVIDIA_RAG.value, "stop": END},
    )
    builder.add_conditional_edges(
        NodeName.NVIDIA_RAG.value,
        route_after_nvidia_rag,
        {"recommend": NodeName.RECOMMENDATION.value, "stop": END},
    )
    builder.add_conditional_edges(
        NodeName.RECOMMENDATION.value,
        route_after_recommendation,
        {"brief": NodeName.BRIEFING.value, "stop": END},
    )
    builder.add_edge(NodeName.BRIEFING.value, END)
    return builder


def compile_analysis_workflow(
    *,
    query_planner: GraphNode,
    retriever: GraphNode,
    extractor: GraphNode,
    startup_classifier: GraphNode,
    evidence_validator: GraphNode,
    nvidia_rag: GraphNode,
    recommendation: GraphNode,
    briefing: GraphNode,
) -> AnalysisWorkflow:
    workflow = create_graph_builder(
        query_planner=query_planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
        evidence_validator=evidence_validator,
        nvidia_rag=nvidia_rag,
        recommendation=recommendation,
        briefing=briefing,
    ).compile()
    return cast(AnalysisWorkflow, workflow)
