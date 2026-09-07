from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.contracts.knowledge_ingestion import NvidiaTechnology
from app.application.services.knowledge_verification import verify_knowledge_base
from app.domain.models import KnowledgeChunk, KnowledgeDocument
from app.infrastructure.retrieval.knowledge_bm25 import KnowledgeBM25Index
from tests.unit.test_knowledge_ingestion import FakeRepository, FakeVectorStore, manifest


async def test_verifier_detects_url_mismatch_and_missing_coverage() -> None:
    repository = FakeRepository()
    document_id = uuid4()
    chunk_id = uuid4()
    repository.document = KnowledgeDocument(
        id=document_id,
        title="NIM",
        source_url="https://www.nvidia.com/nvidia_nim",
        content_type="html",
        content_hash="a" * 64,
        source_key="nvidia-nim",
        technology=NvidiaTechnology.NVIDIA_NIM.value,
        ingested_at=datetime(2026, 9, 7, tzinfo=UTC),
    )
    repository.chunks = [
        KnowledgeChunk(
            id=chunk_id,
            document_id=document_id,
            content="inference",
            chunk_index=0,
            content_hash="b" * 64,
            metadata={"source_url": "https://wrong.example"},
        )
    ]
    vectors = FakeVectorStore()
    vectors.ids = {chunk_id, UUID("00000000-0000-0000-0000-000000000001")}
    vectors.metadata[chunk_id] = {"source_url": "https://vector.example"}

    report = await verify_knowledge_base(manifest(), repository, vectors, KnowledgeBM25Index())

    assert not report.valid
    assert any(item.startswith("source_url_mismatch") for item in report.issues)
    assert any(item.startswith("orphan_vector") for item in report.issues)
    assert any(item.startswith("vector_source_url_mismatch") for item in report.issues)
    assert NvidiaTechnology.CUDA in report.missing_technologies
    assert len(report.bm25_fingerprint) == 64
