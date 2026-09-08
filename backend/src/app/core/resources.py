from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.ports.health import ReadinessProbe
from app.application.ports.providers import ChatModel, EmbeddingModel, Reranker
from app.graph.contracts import AnalysisWorkflow, GraphNode
from app.graph.model_policy import ModelRegistry


@dataclass(slots=True)
class ApplicationResources:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    qdrant: AsyncQdrantClient
    postgres_probe: ReadinessProbe
    qdrant_probe: ReadinessProbe
    llm_fast: ChatModel
    llm_heavy: ChatModel
    model_registry: ModelRegistry
    query_planner: GraphNode
    extractor: GraphNode
    startup_classifier: GraphNode
    evidence_validator: GraphNode
    embedding_model: EmbeddingModel | None
    reranker: Reranker | None
    nvidia_rag: GraphNode
    recommendation: GraphNode
    workflow: AnalysisWorkflow

    async def close(self) -> None:
        if self.embedding_model is not None:
            close = getattr(self.embedding_model, "close", None)
            if close is not None:
                await close()
        await self.qdrant.close()
        await self.engine.dispose()
