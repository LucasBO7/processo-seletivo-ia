from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.application.contracts.knowledge_ingestion import (
    FetchedKnowledgeContent,
    IngestionOutcome,
    KnowledgeContentType,
    KnowledgeSource,
    NvidiaTechnology,
    SourceManifest,
)
from app.application.services.knowledge_ingestion import NvidiaKnowledgeIngestionService
from app.core.config import Settings
from app.infrastructure.ingestion.preparer import DeterministicKnowledgePreparer
from app.infrastructure.persistence.database import create_engine, create_session_factory
from app.infrastructure.persistence.knowledge import SqlAlchemyKnowledgeIngestionRepository
from app.infrastructure.persistence.models import KnowledgeDocumentRow
from app.infrastructure.providers.embeddings import DeterministicEmbeddingModel
from app.infrastructure.vector.knowledge import QdrantKnowledgeVectorStore
from app.infrastructure.vector.qdrant import create_qdrant_client, ensure_collection
from tests.integration.test_persistence import integration_settings

pytestmark = pytest.mark.integration


class IntegrationSourceClient:
    async def fetch(self, source: KnowledgeSource) -> FetchedKnowledgeContent:
        return FetchedKnowledgeContent(
            title="NVIDIA NIM",
            body="# Serving\nOptimized inference service.",
            content_type=KnowledgeContentType.MARKDOWN,
        )


async def test_real_postgres_and_qdrant_ingestion_is_idempotent() -> None:
    settings: Settings = integration_settings()
    engine = create_engine(settings.postgres)
    sessions = create_session_factory(engine)
    qdrant = create_qdrant_client(settings.qdrant)
    suffix = uuid4().hex
    source = KnowledgeSource(
        source_key=f"nvidia-nim-{suffix}",
        technology=NvidiaTechnology.NVIDIA_NIM,
        canonical_url=f"https://www.nvidia.com/{suffix}",
        content_type=KnowledgeContentType.MARKDOWN,
        extractor="fake",
    )
    manifest = SourceManifest(
        version="integration",
        allowed_domains=("www.nvidia.com",),
        sources=tuple(
            source
            if item is NvidiaTechnology.NVIDIA_NIM
            else KnowledgeSource(
                source_key=f"{item.value.replace('_', '-')}-{suffix}",
                technology=item,
                canonical_url=f"https://www.nvidia.com/{item.value}/{suffix}",
                content_type=KnowledgeContentType.MARKDOWN,
                extractor="fake",
            )
            for item in NvidiaTechnology
        ),
    )
    try:
        await ensure_collection(qdrant, settings.qdrant)
        repository = SqlAlchemyKnowledgeIngestionRepository(sessions)
        vector_store = QdrantKnowledgeVectorStore(qdrant, settings.qdrant.collection_name)
        service = NvidiaKnowledgeIngestionService(
            sources=IntegrationSourceClient(),
            preparer=DeterministicKnowledgePreparer(
                chunk_max_characters=200,
                chunk_overlap_characters=20,
            ),
            repository=repository,
            vectors=vector_store,
            embeddings=DeterministicEmbeddingModel(settings.qdrant.embedding_dimension),
            embedding_dimension=settings.qdrant.embedding_dimension,
            embedding_fingerprint=f"integration:{settings.qdrant.embedding_dimension}",
            pipeline_version="integration-v1",
            embedding_batch_size=2,
            clock=lambda: datetime(2026, 9, 7, tzinfo=UTC),
        )

        created = await service.ingest(manifest, source_key=source.source_key)
        unchanged = await service.ingest(manifest, source_key=source.source_key)

        assert created.results[0].outcome is IngestionOutcome.CREATED
        assert unchanged.results[0].outcome is IngestionOutcome.UNCHANGED
        document = await repository.get_by_source_key(source.source_key)
        assert document is not None and document.source_url == str(source.canonical_url)
        chunks = [
            item for item in await repository.list_chunks() if item.document_id == document.id
        ]
        assert chunks and chunks[0].metadata["source_url"] == document.source_url
        assert {item.id for item in chunks} <= await vector_store.list_ids_for_source(
            source.source_key
        )
        metadata = await vector_store.list_metadata()
        assert all(metadata[item.id]["source_url"] == document.source_url for item in chunks)
    finally:
        repository = SqlAlchemyKnowledgeIngestionRepository(sessions)
        stored = await repository.get_by_source_key(source.source_key)
        if stored is not None:
            chunk_ids = {
                item.id for item in await repository.list_chunks() if item.document_id == stored.id
            }
            await QdrantKnowledgeVectorStore(qdrant, settings.qdrant.collection_name).delete(
                tuple(chunk_ids)
            )
            async with sessions.begin() as session:
                await session.execute(
                    delete(KnowledgeDocumentRow).where(KnowledgeDocumentRow.id == stored.id)
                )
        await qdrant.close()
        await engine.dispose()
