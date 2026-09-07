from __future__ import annotations

from typing import Literal, cast

from langgraph.graph import END, START, StateGraph

from app.application.contracts.query_plan import QueryPlanStatus
from app.graph.contracts import AnalysisWorkflow, GraphNode
from app.graph.nodes import NodeName
from app.graph.state import AppState

RouteAfterPlanner = Literal["retrieve", "stop"]
RouteAfterRetriever = Literal["extract", "stop"]
RouteAfterExtractor = Literal["classify", "stop"]
BLOCKING_PLANNER_ERRORS = {
    "query_empty",
    "query_too_long",
    "query_invalid",
    "query_plan_invalid_output",
    "query_planner_unavailable",
}


def route_after_query_planner(state: AppState) -> RouteAfterPlanner:
    """Route only executable, error-free plans to the Retriever."""
    plan = state.get("query_plan")
    has_blocking_error = any(
        error.code in BLOCKING_PLANNER_ERRORS for error in state.get("errors", [])
    )
    if plan is not None and plan.status is QueryPlanStatus.READY and not has_blocking_error:
        return "retrieve"
    return "stop"


def route_after_retriever(state: AppState) -> RouteAfterRetriever:
    """Extract only when a candidate has an attributable, usable source."""
    candidate_ids = {candidate["startup_id"] for candidate in state.get("candidate_startups", [])}
    has_appropriate_source = any(
        source.startup_id in candidate_ids
        and source.source_url.strip()
        and source.excerpt is not None
        and source.excerpt.strip()
        for source in state.get("selected_sources", [])
    )
    return "extract" if candidate_ids and has_appropriate_source else "stop"


def route_after_extractor(state: AppState) -> RouteAfterExtractor:
    """Classify only when the Extractor produced a validated profile."""
    return "classify" if state.get("structured_profiles") else "stop"


def create_graph_builder(
    *,
    query_planner: GraphNode,
    retriever: GraphNode,
    extractor: GraphNode,
    startup_classifier: GraphNode,
) -> StateGraph[AppState, None, AppState, AppState]:
    builder = StateGraph(AppState)
    builder.add_node(NodeName.QUERY_PLANNER.value, query_planner)
    builder.add_node(NodeName.RETRIEVER.value, retriever)
    builder.add_node(NodeName.EXTRACTOR.value, extractor)
    builder.add_node(NodeName.STARTUP_CLASSIFIER.value, startup_classifier)
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
    builder.add_edge(NodeName.STARTUP_CLASSIFIER.value, END)
    return builder


def compile_analysis_workflow(
    *,
    query_planner: GraphNode,
    retriever: GraphNode,
    extractor: GraphNode,
    startup_classifier: GraphNode,
) -> AnalysisWorkflow:
    workflow = create_graph_builder(
        query_planner=query_planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
    ).compile()
    return cast(AnalysisWorkflow, workflow)
