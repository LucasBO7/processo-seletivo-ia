from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.contracts.knowledge_ingestion import (
    NormalizedKnowledgeDocument,
    PreparedKnowledgeChunk,
)
from app.domain.models import KnowledgeChunk, KnowledgeDocument
from app.infrastructure.persistence.models import KnowledgeChunkRow, KnowledgeDocumentRow
from app.infrastructure.persistence.repositories import (
    _knowledge_chunk_from_row,
    _knowledge_document_from_row,
)


class SqlAlchemyKnowledgeIngestionRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_by_source_key(self, source_key: str) -> KnowledgeDocument | None:
        statement = select(KnowledgeDocumentRow).where(
            KnowledgeDocumentRow.source_key == source_key
        )
        async with self._sessions() as session:
            row = await session.scalar(statement)
        return _knowledge_document_from_row(row) if row else None

    async def replace_revision(
        self,
        document: NormalizedKnowledgeDocument,
        chunks: Sequence[PreparedKnowledgeChunk],
        *,
        revision: int,
    ) -> tuple[UUID, ...]:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(KnowledgeDocumentRow)
                .where(KnowledgeDocumentRow.source_key == document.source_key)
                .with_for_update()
            )
            old_ids: tuple[UUID, ...] = ()
            if row is None:
                row = KnowledgeDocumentRow(
                    id=document.document_id,
                    source_key=document.source_key,
                    title=document.title,
                    source_url=document.source_url,
                    technology=document.technology.value,
                    content_type=document.content_type.value,
                    published_at=document.published_at,
                    content_hash=document.content_hash,
                    revision=revision,
                    pipeline_version=document.pipeline_version,
                    ingested_at=document.ingested_at,
                    created_at=document.ingested_at,
                    updated_at=document.ingested_at,
                )
                session.add(row)
                await session.flush()
            else:
                old_ids = tuple(
                    await session.scalars(
                        select(KnowledgeChunkRow.id).where(KnowledgeChunkRow.document_id == row.id)
                    )
                )
                await session.execute(
                    delete(KnowledgeChunkRow).where(KnowledgeChunkRow.document_id == row.id)
                )
                row.title = document.title
                row.source_url = document.source_url
                row.technology = document.technology.value
                row.content_type = document.content_type.value
                row.published_at = document.published_at
                row.content_hash = document.content_hash
                row.revision = revision
                row.pipeline_version = document.pipeline_version
                row.ingested_at = document.ingested_at
                row.updated_at = document.ingested_at
            for chunk in chunks:
                session.add(
                    KnowledgeChunkRow(
                        id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        metadata_json=chunk.metadata,
                        content_hash=chunk.content_hash,
                        created_at=document.ingested_at,
                        updated_at=document.ingested_at,
                    )
                )
        new_ids = {item.chunk_id for item in chunks}
        return tuple(item for item in old_ids if item not in new_ids)

    async def list_documents(self) -> list[KnowledgeDocument]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(KnowledgeDocumentRow).order_by(KnowledgeDocumentRow.source_key)
                )
            ).all()
        return [_knowledge_document_from_row(row) for row in rows]

    async def list_chunks(self) -> list[KnowledgeChunk]:
        statement = select(KnowledgeChunkRow).order_by(
            KnowledgeChunkRow.document_id, KnowledgeChunkRow.chunk_index
        )
        async with self._sessions() as session:
            rows = (await session.scalars(statement)).all()
        return [_knowledge_chunk_from_row(row) for row in rows]
