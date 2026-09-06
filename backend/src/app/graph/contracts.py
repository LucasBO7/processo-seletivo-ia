from __future__ import annotations

from typing import Protocol

from app.graph.state import AppState


class GraphNode(Protocol):
    async def __call__(self, state: AppState) -> AppState:
        """Return only the state fields updated by this node."""
        ...
