from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

from app.application.contracts.knowledge_ingestion import PreparedKnowledgeChunk


class QdrantKnowledgeVectorStore:
    def __init__(self, client: AsyncQdrantClient, collection_name: str) -> None:
        self._client = client
        self._collection_name = collection_name

    async def upsert(
        self, chunks: Sequence[PreparedKnowledgeChunk], vectors: Sequence[Sequence[float]]
    ) -> None:
        if not chunks:
            return
        await self._client.upsert(
            collection_name=self._collection_name,
            points=[
                models.PointStruct(
                    id=str(chunk.chunk_id),
                    vector=list(vector),
                    payload={
                        "document_id": str(chunk.document_id),
                        "source_key": chunk.metadata["source_key"],
                        "technology": chunk.metadata["technology"],
                        "source_url": chunk.metadata["source_url"],
                        "source_section": chunk.metadata["source_section"],
                        "content_hash": chunk.content_hash,
                        "pipeline_version": chunk.metadata["pipeline_version"],
                        "embedding_fingerprint": chunk.metadata["embedding_fingerprint"],
                    },
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
            wait=True,
        )

    async def delete(self, chunk_ids: Sequence[UUID]) -> None:
        if not chunk_ids:
            return
        await self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.PointIdsList(points=[str(item) for item in chunk_ids]),
            wait=True,
        )

    async def list_ids(self) -> set[UUID]:
        return await self._scroll_ids()

    async def list_ids_for_source(self, source_key: str) -> set[UUID]:
        return await self._scroll_ids(
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_key", match=models.MatchValue(value=source_key)
                    )
                ]
            )
        )

    async def list_metadata(self) -> dict[UUID, dict[str, object]]:
        result: dict[UUID, dict[str, object]] = {}
        offset: models.ExtendedPointId | None = None
        while True:
            points, offset = await self._client.scroll(
                collection_name=self._collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                result[UUID(str(point.id))] = dict(point.payload or {})
            if offset is None:
                return result

    async def _scroll_ids(self, query_filter: models.Filter | None = None) -> set[UUID]:
        result: set[UUID] = set()
        offset: models.ExtendedPointId | None = None
        while True:
            points, offset = await self._client.scroll(
                collection_name=self._collection_name,
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
                scroll_filter=query_filter,
            )
            result.update(UUID(str(point.id)) for point in points)
            if offset is None:
                return result
