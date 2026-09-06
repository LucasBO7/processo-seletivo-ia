from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.ports.health import ReadinessProbe
from app.application.ports.providers import ChatModel
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

    async def close(self) -> None:
        await self.qdrant.close()
        await self.engine.dispose()
