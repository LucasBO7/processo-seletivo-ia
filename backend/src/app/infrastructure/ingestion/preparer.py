from __future__ import annotations

from datetime import datetime

from app.application.contracts.knowledge_ingestion import (
    FetchedKnowledgeContent,
    KnowledgeSource,
    NormalizedKnowledgeDocument,
    PreparedKnowledgeChunk,
)
from app.infrastructure.ingestion.chunking import chunk_document
from app.infrastructure.ingestion.normalization import normalize_document


class DeterministicKnowledgePreparer:
    def __init__(self, *, chunk_max_characters: int, chunk_overlap_characters: int) -> None:
        self._chunk_max_characters = chunk_max_characters
        self._chunk_overlap_characters = chunk_overlap_characters

    def prepare(
        self,
        source: KnowledgeSource,
        fetched: FetchedKnowledgeContent,
        *,
        ingested_at: datetime,
        pipeline_version: str,
        embedding_fingerprint: str,
    ) -> tuple[NormalizedKnowledgeDocument, tuple[PreparedKnowledgeChunk, ...]]:
        document = normalize_document(
            source,
            fetched,
            ingested_at=ingested_at,
            pipeline_version=pipeline_version,
        )
        chunks = chunk_document(
            document,
            max_characters=self._chunk_max_characters,
            overlap_characters=self._chunk_overlap_characters,
            embedding_fingerprint=embedding_fingerprint,
        )
        return document, chunks
