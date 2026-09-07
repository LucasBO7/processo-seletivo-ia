from __future__ import annotations

from typing import Literal, cast

from langgraph.graph import END, START, StateGraph

from app.application.contracts.query_plan import QueryPlanStatus
from app.graph.contracts import AnalysisWorkflow, GraphNode
from app.graph.nodes import NodeName
from app.graph.state import AppState

RouteAfterPlanner = Literal["retrieve", "stop"]
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


def create_graph_builder(
    *, query_planner: GraphNode, retriever: GraphNode
) -> StateGraph[AppState, None, AppState, AppState]:
    builder = StateGraph(AppState)
    builder.add_node(NodeName.QUERY_PLANNER.value, query_planner)
    builder.add_node(NodeName.RETRIEVER.value, retriever)
    builder.add_edge(START, NodeName.QUERY_PLANNER.value)
    builder.add_conditional_edges(
        NodeName.QUERY_PLANNER.value,
        route_after_query_planner,
        {"retrieve": NodeName.RETRIEVER.value, "stop": END},
    )
    builder.add_edge(NodeName.RETRIEVER.value, END)
    return builder


def compile_analysis_workflow(
    *, query_planner: GraphNode, retriever: GraphNode
) -> AnalysisWorkflow:
    workflow = create_graph_builder(query_planner=query_planner, retriever=retriever).compile()
    return cast(AnalysisWorkflow, workflow)
