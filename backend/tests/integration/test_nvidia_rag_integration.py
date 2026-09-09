from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.application.contracts.evidence_validation import ValidatedStartupProfile
from app.application.contracts.extraction import ExtractedFact, ExtractionSource, ProfileField
from app.application.contracts.knowledge_ingestion import (
    KnowledgeContentType,
    NormalizedKnowledgeDocument,
    NvidiaTechnology,
    PreparedKnowledgeChunk,
)
from app.application.contracts.nvidia_rag import NvidiaContextStatus
from app.core.config import NvidiaRagConfig, Settings
from app.graph.agents.nvidia_rag import NvidiaRagAgent
from app.graph.state import AppState
from app.infrastructure.persistence.database import create_engine, create_session_factory
from app.infrastructure.persistence.knowledge import SqlAlchemyKnowledgeIngestionRepository
from app.infrastructure.persistence.models import KnowledgeDocumentRow
from app.infrastructure.retrieval.knowledge_bm25 import KnowledgeBM25Index
from app.infrastructure.vector.knowledge import QdrantKnowledgeVectorStore
from app.infrastructure.vector.qdrant import create_qdrant_client, ensure_collection
from tests.fakes.providers import FakeReranker
from tests.integration.test_persistence import integration_settings

pytestmark = pytest.mark.integration


class FixedEmbeddingModel:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.vector.copy() for _ in texts]


async def test_nvidia_rag_reads_postgres_and_searches_real_qdrant() -> None:
    settings: Settings = integration_settings()
    engine = create_engine(settings.postgres)
    sessions = create_session_factory(engine)
    qdrant = create_qdrant_client(settings.qdrant)
    suffix = uuid4().hex
    document_id = uuid4()
    chunk_id = uuid4()
    ingested_at = datetime(2026, 9, 7, tzinfo=UTC)
    source_url = f"https://docs.nvidia.com/integration/{suffix}"
    repository = SqlAlchemyKnowledgeIngestionRepository(sessions)
    qdrant_config = settings.qdrant.model_copy(
        update={"collection_name": f"nvidia_rag_test_{suffix}"}
    )
    vector_store = QdrantKnowledgeVectorStore(qdrant, qdrant_config.collection_name)
    try:
        await ensure_collection(qdrant, qdrant_config)
        document = NormalizedKnowledgeDocument(
            document_id=document_id,
            source_key=f"triton-{suffix}",
            title="Triton Integration Fixture",
            technology=NvidiaTechnology.TRITON_INFERENCE_SERVER,
            source_url=source_url,
            content_type=KnowledgeContentType.TEXT,
            content="Triton provides optimized inference serving and dynamic batching.",
            published_at=None,
            ingested_at=ingested_at,
            content_hash="a" * 64,
            pipeline_version="integration-v1",
        )
        chunk = PreparedKnowledgeChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_index=0,
            content=document.content,
            content_hash="b" * 64,
            metadata={
                "source_key": document.source_key,
                "technology": document.technology.value,
                "source_url": source_url,
                "source_section": "Serving",
                "start_offset": 0,
                "end_offset": len(document.content),
                "pipeline_version": document.pipeline_version,
                "embedding_fingerprint": "integration",
            },
        )
        await repository.replace_revision(document, [chunk], revision=1)
        vector = [1.0, *([0.0] * (settings.qdrant.embedding_dimension - 1))]
        await vector_store.upsert([chunk], [vector])

        startup_id = uuid4()
        source = ExtractionSource(
            startup_id=startup_id,
            source_id=uuid4(),
            source_url="https://startup.example/evidence",
        )
        profile = ValidatedStartupProfile(
            startup_id=startup_id,
            name="Integration Startup",
            technical_needs=[ExtractedFact(value="optimized inference serving", sources=[source])],
            unknown_fields=[
                field for field in ProfileField if field is not ProfileField.TECHNICAL_NEEDS
            ],
        )
        agent = NvidiaRagAgent(
            repository=repository,
            vector_search=vector_store,
            lexical_search=KnowledgeBM25Index(),
            embedding_model=FixedEmbeddingModel(vector),
            reranker=FakeReranker(),
            config=NvidiaRagConfig(
                vector_top_k=1,
                lexical_top_k=1,
                fused_top_k=2,
                rerank_top_n=2,
                min_relevant_chunks=1,
                min_distinct_documents=1,
                min_reranker_score=0,
            ),
            embedding_dimension=settings.qdrant.embedding_dimension,
        )

        result = await agent(AppState(validated_profiles=[profile]))

        context = result["nvidia_contexts"][0]
        assert context.sufficiency.status is NvidiaContextStatus.SUFFICIENT
        retrieved = next(item for item in context.chunks if item.chunk_id == chunk_id)
        assert retrieved.source_url == source_url
    finally:
        if await qdrant.collection_exists(qdrant_config.collection_name):
            await qdrant.delete_collection(qdrant_config.collection_name)
        async with sessions.begin() as session:
            await session.execute(
                delete(KnowledgeDocumentRow).where(KnowledgeDocumentRow.id == document_id)
            )
        await qdrant.close()
        await engine.dispose()
