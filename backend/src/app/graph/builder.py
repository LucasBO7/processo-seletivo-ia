from langgraph.graph import StateGraph

from app.graph.state import StartupRadarState


def create_graph_builder() -> StateGraph[
    StartupRadarState, None, StartupRadarState, StartupRadarState
]:
    """Create an empty builder; business nodes and edges require a future spec."""
    return StateGraph(StartupRadarState)
