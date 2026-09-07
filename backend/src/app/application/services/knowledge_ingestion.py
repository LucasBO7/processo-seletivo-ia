from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from time import perf_counter

from app.application.contracts.knowledge_ingestion import (
    IngestionOutcome,
    IngestionReport,
    KnowledgeSource,
    PreparedKnowledgeChunk,
    SourceIngestionResult,
    SourceManifest,
)
from app.application.ports.knowledge import (
    KnowledgeDocumentPreparer,
    KnowledgeIngestionRepository,
    KnowledgeSourceClient,
    KnowledgeVectorStore,
)
from app.application.ports.providers import EmbeddingModel

logger = logging.getLogger(__name__)


class NvidiaKnowledgeIngestionService:
    def __init__(
        self,
        *,
        sources: KnowledgeSourceClient,
        preparer: KnowledgeDocumentPreparer,
        repository: KnowledgeIngestionRepository,
        vectors: KnowledgeVectorStore,
        embeddings: EmbeddingModel,
        embedding_dimension: int,
        embedding_fingerprint: str,
        pipeline_version: str,
        embedding_batch_size: int,
        max_concurrency: int = 4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sources = sources
        self._preparer = preparer
        self._repository = repository
        self._vectors = vectors
        self._embeddings = embeddings
        self._embedding_dimension = embedding_dimension
        self._embedding_fingerprint = embedding_fingerprint
        self._pipeline_version = pipeline_version
        self._embedding_batch_size = embedding_batch_size
        self._max_concurrency = max_concurrency
        self._clock = clock

    async def ingest(
        self,
        manifest: SourceManifest,
        *,
        dry_run: bool = False,
        technology: str | None = None,
        source_key: str | None = None,
    ) -> IngestionReport:
        started = perf_counter()
        selected = [
            item
            for item in manifest.sources
            if item.enabled
            and (technology is None or item.technology.value == technology)
            and (source_key is None or item.source_key == source_key)
        ]
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def ingest_one(item: KnowledgeSource) -> SourceIngestionResult:
            async with semaphore:
                return await self._ingest_source(item, dry_run=dry_run)

        results = await asyncio.gather(*(ingest_one(item) for item in selected))
        report = IngestionReport(
            manifest_version=manifest.version,
            dry_run=dry_run,
            results=tuple(results),
        )
        logger.info(
            "nvidia_knowledge_ingestion_completed",
            extra={
                "manifest_version": manifest.version,
                "dry_run": dry_run,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "sources": len(results),
                "ingestion_created": report.count(IngestionOutcome.CREATED),
                "ingestion_updated": report.count(IngestionOutcome.UPDATED),
                "ingestion_unchanged": report.count(IngestionOutcome.UNCHANGED),
                "ingestion_failed": report.count(IngestionOutcome.FAILED),
            },
        )
        return report

    async def _ingest_source(
        self, source: KnowledgeSource, *, dry_run: bool
    ) -> SourceIngestionResult:
        try:
            try:
                fetched = await self._sources.fetch(source)
            except Exception as error:
                if str(error).startswith("knowledge_"):
                    raise
                raise RuntimeError("knowledge_fetch_failed") from error
            document, chunks = self._preparer.prepare(
                source,
                fetched,
                ingested_at=self._clock(),
                pipeline_version=self._pipeline_version,
                embedding_fingerprint=self._embedding_fingerprint,
            )
            current = await self._repository.get_by_source_key(source.source_key)
            if (
                current
                and current.content_hash == document.content_hash
                and current.source_url == document.source_url
                and current.pipeline_version == document.pipeline_version
            ):
                stored = [
                    item
                    for item in await self._repository.list_chunks()
                    if item.document_id == current.id
                ]
                source_vector_ids = await self._vectors.list_ids_for_source(source.source_key)
                expected_ids = {item.id for item in stored}
                if source_vector_ids != expected_ids and not dry_run:
                    prepared = tuple(
                        PreparedKnowledgeChunk(
                            chunk_id=item.id,
                            document_id=item.document_id,
                            chunk_index=item.chunk_index,
                            content=item.content,
                            content_hash=item.content_hash,
                            metadata=item.metadata,
                        )
                        for item in stored
                    )
                    vectors = await self._embed_batches([item.content for item in prepared])
                    try:
                        await self._vectors.upsert(prepared, vectors)
                        await self._vectors.delete(tuple(source_vector_ids - expected_ids))
                    except Exception as error:
                        raise RuntimeError("knowledge_vector_sync_failed") from error
                return SourceIngestionResult(
                    source_key=source.source_key,
                    outcome=IngestionOutcome.UNCHANGED,
                    document_id=current.id,
                    chunks=len(stored),
                )
            vectors = await self._embed_batches([item.content for item in chunks])
            if dry_run:
                return SourceIngestionResult(
                    source_key=source.source_key,
                    outcome=IngestionOutcome.UPDATED if current else IngestionOutcome.CREATED,
                    document_id=document.document_id,
                    chunks=len(chunks),
                )
            revision = (current.revision + 1) if current else 1
            try:
                stale_ids = await self._repository.replace_revision(
                    document, chunks, revision=revision
                )
            except Exception as error:
                raise RuntimeError("knowledge_persistence_failed") from error
            try:
                await self._vectors.upsert(chunks, vectors)
                await self._vectors.delete(stale_ids)
            except Exception as error:
                raise RuntimeError("knowledge_vector_sync_failed") from error
            return SourceIngestionResult(
                source_key=source.source_key,
                outcome=IngestionOutcome.UPDATED if current else IngestionOutcome.CREATED,
                document_id=document.document_id,
                chunks=len(chunks),
            )
        except Exception as error:
            code = str(error)
            if not code.startswith("knowledge_"):
                code = "knowledge_fetch_failed"
            return SourceIngestionResult(
                source_key=source.source_key,
                outcome=IngestionOutcome.FAILED,
                error_code=code,
            )

    async def _embed_batches(self, texts: Sequence[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for start in range(0, len(texts), self._embedding_batch_size):
            batch = texts[start : start + self._embedding_batch_size]
            vectors = await self._embeddings.embed(batch)
            if len(vectors) != len(batch):
                raise ValueError("knowledge_embedding_invalid")
            for vector in vectors:
                if len(vector) != self._embedding_dimension or not all(
                    math.isfinite(value) for value in vector
                ):
                    raise ValueError("knowledge_embedding_invalid")
            result.extend(vectors)
        return result
