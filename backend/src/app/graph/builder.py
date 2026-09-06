from app.graph.agents import query_planner, retriever
from langgraph.graph import END, START, StateGraph

from app.graph.state import AppState


def create_graph_builder() -> StateGraph[AppState, None, AppState, AppState]:
    builder = StateGraph[AppState, None, AppState, AppState]()

    builder.add_node("query_planner", query_planner)
    builder.add_node("retriever", retriever)

    builder.add_edge(START, "query_planner")

    builder.add_conditional_edges(
        "query_planner",
        route_after_query_planner,
        {
            "retrieve": "retriever",
            "stop": END,
        },
    )

    builder.add_edge("retriever", END)

    graph = builder.compile()

    return StateGraph(AppState)
