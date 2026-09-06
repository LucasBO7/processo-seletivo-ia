from __future__ import annotations

import os
from uuid import uuid4

import pytest
from qdrant_client import models
from sqlalchemy import inspect

from app.core.config import Settings
from app.domain.models import KnowledgeChunk, KnowledgeDocument, Startup, StartupDocument
from app.infrastructure.persistence.database import create_engine, create_session_factory
from app.infrastructure.persistence.repositories import (
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyKnowledgeDocumentRepository,
    SqlAlchemyStartupDocumentRepository,
    SqlAlchemyStartupRepository,
)
from app.infrastructure.vector.qdrant import create_qdrant_client, ensure_collection

pytestmark = pytest.mark.integration


def integration_settings() -> Settings:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Defina RUN_INTEGRATION_TESTS=1 para executar integrações reais.")
    return Settings()


async def test_schema_repositories_and_qdrant_are_consistent() -> None:
    settings = integration_settings()
    engine = create_engine(settings.postgres)
    sessions = create_session_factory(engine)
    qdrant = create_qdrant_client(settings.qdrant)
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
        assert {
            "startups",
            "startup_documents",
            "analysis_runs",
            "knowledge_documents",
            "knowledge_chunks",
        } <= tables

        startup_repository = SqlAlchemyStartupRepository(sessions)
        startup_document_repository = SqlAlchemyStartupDocumentRepository(sessions)
        knowledge_repository = SqlAlchemyKnowledgeDocumentRepository(sessions)
        chunk_repository = SqlAlchemyKnowledgeChunkRepository(sessions)

        suffix = uuid4().hex
        startup = Startup(name=f"Startup {suffix}")
        await startup_repository.add(startup)
        evidence = StartupDocument(
            startup_id=startup.id,
            document_type="site",
            title="Página oficial",
            content_text="Evidência pública da startup.",
            source_url=f"https://example.com/{suffix}",
        )
        await startup_document_repository.add(evidence)
        assert (await startup_repository.get(startup.id)) == startup
        assert (await startup_document_repository.list_for_startup(startup.id))[0] == evidence

        knowledge = KnowledgeDocument(
            title="NVIDIA NIM",
            source_url=f"https://nvidia.com/{suffix}",
            content_type="documentation",
            content_hash=suffix.ljust(64, "0")[:64],
        )
        await knowledge_repository.add(knowledge)
        chunk = KnowledgeChunk(
            document_id=knowledge.id,
            content="NIM disponibiliza microsserviços de inferência.",
            chunk_index=0,
            content_hash=("a" + suffix).ljust(64, "0")[:64],
            metadata={"source_url": knowledge.source_url},
        )
        await chunk_repository.add(chunk)
        assert (await knowledge_repository.get(knowledge.id)) == knowledge
        assert (await chunk_repository.get(chunk.id)) == chunk

        await ensure_collection(qdrant, settings.qdrant)
        await ensure_collection(qdrant, settings.qdrant)
        await qdrant.upsert(
            collection_name=settings.qdrant.collection_name,
            points=[
                models.PointStruct(
                    id=str(chunk.id),
                    vector=[0.1] * settings.qdrant.embedding_dimension,
                    payload={"document_id": str(knowledge.id)},
                )
            ],
            wait=True,
        )
        points = await qdrant.retrieve(
            collection_name=settings.qdrant.collection_name,
            ids=[str(chunk.id)],
        )
        assert str(points[0].id) == str(chunk.id)
        assert str((await chunk_repository.list_for_document(knowledge.id))[0].id) == str(
            points[0].id
        )
    finally:
        await qdrant.close()
        await engine.dispose()
