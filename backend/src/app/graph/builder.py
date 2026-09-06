from langgraph.graph import StateGraph

from app.graph.state import AppState


def create_graph_builder() -> StateGraph[
    AppState, None, AppState, AppState
]:
    """Create an empty builder; business nodes and edges require a future spec."""
    return StateGraph(AppState)
