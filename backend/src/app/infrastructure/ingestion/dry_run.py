from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.application.contracts.knowledge_ingestion import (
    NormalizedKnowledgeDocument,
    PreparedKnowledgeChunk,
)
from app.domain.models import KnowledgeChunk, KnowledgeDocument


class DryRunKnowledgeRepository:
    async def get_by_source_key(self, source_key: str) -> KnowledgeDocument | None:
        del source_key
        return None

    async def replace_revision(
        self,
        document: NormalizedKnowledgeDocument,
        chunks: Sequence[PreparedKnowledgeChunk],
        *,
        revision: int,
    ) -> tuple[UUID, ...]:
        del document, chunks, revision
        raise AssertionError("dry-run cannot write to PostgreSQL")

    async def list_documents(self) -> list[KnowledgeDocument]:
        return []

    async def list_chunks(self) -> list[KnowledgeChunk]:
        return []


class DryRunKnowledgeVectorStore:
    async def upsert(
        self, chunks: Sequence[PreparedKnowledgeChunk], vectors: Sequence[Sequence[float]]
    ) -> None:
        del chunks, vectors
        raise AssertionError("dry-run cannot write to Qdrant")

    async def delete(self, chunk_ids: Sequence[UUID]) -> None:
        del chunk_ids
        raise AssertionError("dry-run cannot write to Qdrant")

    async def list_ids(self) -> set[UUID]:
        return set()

    async def list_ids_for_source(self, source_key: str) -> set[UUID]:
        del source_key
        return set()

    async def list_metadata(self) -> dict[UUID, dict[str, object]]:
        return {}
