from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.application.contracts.knowledge_ingestion import (
    FetchedKnowledgeContent,
    IngestionOutcome,
    KnowledgeContentType,
    KnowledgeSource,
    NvidiaTechnology,
    SourceManifest,
)
from app.application.ports.knowledge import KnowledgeSourceClient
from app.application.ports.providers import EmbeddingModel
from app.application.services.knowledge_ingestion import NvidiaKnowledgeIngestionService
from app.domain.models import KnowledgeChunk, KnowledgeDocument
from app.infrastructure.ingestion.preparer import DeterministicKnowledgePreparer
from app.infrastructure.providers.embeddings import DeterministicEmbeddingModel


class FakeSourceClient:
    def __init__(self, body: str = "# NIM\nInference service") -> None:
        self.body = body

    async def fetch(self, source: KnowledgeSource) -> FetchedKnowledgeContent:
        return FetchedKnowledgeContent(
            title=source.source_key,
            body=self.body,
            content_type=KnowledgeContentType.MARKDOWN,
        )


class FakeRepository:
    def __init__(self) -> None:
        self.document: KnowledgeDocument | None = None
        self.chunks: list[KnowledgeChunk] = []
        self.replacements = 0

    async def get_by_source_key(self, source_key: str) -> KnowledgeDocument | None:
        return self.document if self.document and self.document.source_key == source_key else None

    async def replace_revision(self, document, chunks, *, revision: int):  # type: ignore[no-untyped-def]
        old = tuple(item.id for item in self.chunks)
        self.document = KnowledgeDocument(
            id=document.document_id,
            title=document.title,
            source_url=document.source_url,
            content_type=document.content_type.value,
            content_hash=document.content_hash,
            published_at=document.published_at,
            source_key=document.source_key,
            technology=document.technology.value,
            revision=revision,
            pipeline_version=document.pipeline_version,
            ingested_at=document.ingested_at,
        )
        self.chunks = [
            KnowledgeChunk(
                id=item.chunk_id,
                document_id=item.document_id,
                content=item.content,
                chunk_index=item.chunk_index,
                content_hash=item.content_hash,
                metadata=item.metadata,
                created_at=document.ingested_at,
                updated_at=document.ingested_at,
            )
            for item in chunks
        ]
        self.replacements += 1
        new = {item.id for item in self.chunks}
        return tuple(item for item in old if item not in new)

    async def list_documents(self) -> list[KnowledgeDocument]:
        return [self.document] if self.document else []

    async def list_chunks(self) -> list[KnowledgeChunk]:
        return self.chunks


class FakeVectorStore:
    def __init__(self) -> None:
        self.ids: set[UUID] = set()
        self.deleted: list[UUID] = []
        self.metadata: dict[UUID, dict[str, object]] = {}

    async def upsert(self, chunks, vectors) -> None:  # type: ignore[no-untyped-def]
        assert len(chunks) == len(vectors)
        self.ids.update(item.chunk_id for item in chunks)
        self.metadata.update({item.chunk_id: dict(item.metadata) for item in chunks})

    async def delete(self, chunk_ids) -> None:  # type: ignore[no-untyped-def]
        self.deleted.extend(chunk_ids)
        self.ids.difference_update(chunk_ids)
        for chunk_id in chunk_ids:
            self.metadata.pop(chunk_id, None)

    async def list_ids(self) -> set[UUID]:
        return self.ids

    async def list_ids_for_source(self, source_key: str) -> set[UUID]:
        return {
            item for item in self.ids if self.metadata.get(item, {}).get("source_key") == source_key
        }

    async def list_metadata(self) -> dict[UUID, dict[str, object]]:
        return self.metadata


class FailingOnceVectorStore(FakeVectorStore):
    def __init__(self) -> None:
        super().__init__()
        self.fail = True

    async def upsert(self, chunks, vectors) -> None:  # type: ignore[no-untyped-def]
        if self.fail:
            self.fail = False
            raise RuntimeError("provider details")
        await super().upsert(chunks, vectors)


class InvalidEmbeddingModel:
    async def embed(self, texts):  # type: ignore[no-untyped-def]
        return [[float("nan")]] * len(texts)


def manifest() -> SourceManifest:
    sources = tuple(
        KnowledgeSource(
            source_key=item.value.replace("_", "-"),
            technology=item,
            canonical_url=f"https://www.nvidia.com/{item.value}",
            content_type=KnowledgeContentType.MARKDOWN,
            extractor="fake",
        )
        for item in NvidiaTechnology
    )
    return SourceManifest(version="test", allowed_domains=("www.nvidia.com",), sources=sources)


def service(
    repository: FakeRepository,
    vectors: FakeVectorStore,
    source_client: KnowledgeSourceClient | None = None,
    embeddings: EmbeddingModel | None = None,
) -> NvidiaKnowledgeIngestionService:
    return NvidiaKnowledgeIngestionService(
        sources=source_client or FakeSourceClient(),
        preparer=DeterministicKnowledgePreparer(
            chunk_max_characters=100,
            chunk_overlap_characters=10,
        ),
        repository=repository,
        vectors=vectors,
        embeddings=embeddings or DeterministicEmbeddingModel(2),
        embedding_dimension=2,
        embedding_fingerprint="fake:2",
        pipeline_version="v1",
        embedding_batch_size=2,
        clock=lambda: datetime(2026, 9, 7, tzinfo=UTC),
    )


async def test_ingestion_is_idempotent_and_preserves_source_url() -> None:
    repository = FakeRepository()
    vectors = FakeVectorStore()
    ingestion = service(repository, vectors)

    first = await ingestion.ingest(manifest(), source_key="nvidia-nim")
    second = await ingestion.ingest(manifest(), source_key="nvidia-nim")

    assert first.results[0].outcome is IngestionOutcome.CREATED
    assert second.results[0].outcome is IngestionOutcome.UNCHANGED
    assert repository.replacements == 1
    assert repository.document is not None
    assert repository.document.source_url == "https://www.nvidia.com/nvidia_nim"
    assert repository.chunks[0].metadata["source_url"] == repository.document.source_url


async def test_update_increments_revision_and_removes_stale_vectors() -> None:
    repository = FakeRepository()
    vectors = FakeVectorStore()
    source_client = FakeSourceClient()
    ingestion = service(repository, vectors, source_client)
    await ingestion.ingest(manifest(), source_key="nvidia-nim")
    old_ids = set(vectors.ids)

    source_client.body = "# NIM\nUpdated inference service"
    result = await ingestion.ingest(manifest(), source_key="nvidia-nim")

    assert result.results[0].outcome is IngestionOutcome.UPDATED
    assert repository.document is not None and repository.document.revision == 2
    assert set(vectors.deleted) == old_ids


async def test_dry_run_does_not_write() -> None:
    repository = FakeRepository()
    vectors = FakeVectorStore()

    result = await service(repository, vectors).ingest(
        manifest(), dry_run=True, source_key="nvidia-nim"
    )

    assert result.results[0].outcome is IngestionOutcome.CREATED
    assert repository.replacements == 0
    assert not vectors.ids


async def test_retry_reconciles_vector_failure_without_new_revision() -> None:
    repository = FakeRepository()
    vectors = FailingOnceVectorStore()
    ingestion = service(repository, vectors)

    failed = await ingestion.ingest(manifest(), source_key="nvidia-nim")
    recovered = await ingestion.ingest(manifest(), source_key="nvidia-nim")

    assert failed.results[0].outcome is IngestionOutcome.FAILED
    assert failed.results[0].error_code == "knowledge_vector_sync_failed"
    assert recovered.results[0].outcome is IngestionOutcome.UNCHANGED
    assert repository.document is not None and repository.document.revision == 1
    assert vectors.ids == {item.id for item in repository.chunks}


async def test_invalid_embedding_aborts_before_persistence() -> None:
    repository = FakeRepository()
    vectors = FakeVectorStore()
    ingestion = service(repository, vectors, embeddings=InvalidEmbeddingModel())

    result = await ingestion.ingest(manifest(), source_key="nvidia-nim")

    assert result.results[0].outcome is IngestionOutcome.FAILED
    assert result.results[0].error_code == "knowledge_embedding_invalid"
    assert repository.replacements == 0
