from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.contracts.knowledge_ingestion import (
    FetchedKnowledgeContent,
    KnowledgeSource,
    NormalizedKnowledgeDocument,
    PreparedKnowledgeChunk,
)
from app.domain.models import KnowledgeChunk, KnowledgeDocument


@dataclass(frozen=True, slots=True)
class KnowledgeSearchHit:
    chunk_id: UUID
    score: float


class KnowledgeSourceClient(Protocol):
    async def fetch(self, source: KnowledgeSource) -> FetchedKnowledgeContent: ...


class KnowledgeDocumentPreparer(Protocol):
    def prepare(
        self,
        source: KnowledgeSource,
        fetched: FetchedKnowledgeContent,
        *,
        ingested_at: datetime,
        pipeline_version: str,
        embedding_fingerprint: str,
    ) -> tuple[NormalizedKnowledgeDocument, tuple[PreparedKnowledgeChunk, ...]]: ...


class KnowledgeIngestionRepository(Protocol):
    async def get_by_source_key(self, source_key: str) -> KnowledgeDocument | None: ...

    async def replace_revision(
        self,
        document: NormalizedKnowledgeDocument,
        chunks: Sequence[PreparedKnowledgeChunk],
        *,
        revision: int,
    ) -> tuple[UUID, ...]: ...

    async def list_documents(self) -> list[KnowledgeDocument]: ...

    async def list_chunks(self) -> list[KnowledgeChunk]: ...


class KnowledgeVectorStore(Protocol):
    async def upsert(
        self, chunks: Sequence[PreparedKnowledgeChunk], vectors: Sequence[Sequence[float]]
    ) -> None: ...

    async def delete(self, chunk_ids: Sequence[UUID]) -> None: ...

    async def list_ids(self) -> set[UUID]: ...

    async def list_ids_for_source(self, source_key: str) -> set[UUID]: ...

    async def list_metadata(self) -> dict[UUID, dict[str, object]]: ...


class KnowledgeLexicalIndex(Protocol):
    def build_and_fingerprint(self, chunks: Sequence[KnowledgeChunk]) -> str: ...


class KnowledgeRetrievalRepository(Protocol):
    async def list_documents(self) -> list[KnowledgeDocument]: ...

    async def list_chunks(self) -> list[KnowledgeChunk]: ...


class KnowledgeVectorSearch(Protocol):
    async def search(self, vector: Sequence[float], *, limit: int) -> list[KnowledgeSearchHit]: ...


class KnowledgeLexicalSearch(Protocol):
    def search(
        self, query: str, chunks: Sequence[KnowledgeChunk], *, limit: int
    ) -> list[KnowledgeSearchHit]: ...
