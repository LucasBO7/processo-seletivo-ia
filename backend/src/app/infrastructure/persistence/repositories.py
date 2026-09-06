from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.models import (
    AnalysisRun,
    AnalysisStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    Startup,
    StartupDocument,
)
from app.infrastructure.persistence.models import (
    AnalysisRunRow,
    KnowledgeChunkRow,
    KnowledgeDocumentRow,
    StartupDocumentRow,
    StartupRow,
)


class SqlAlchemyStartupRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, startup: Startup) -> Startup:
        async with self._sessions.begin() as session:
            session.add(StartupRow(**_startup_values(startup)))
        return startup

    async def get(self, startup_id: UUID) -> Startup | None:
        async with self._sessions() as session:
            row = await session.get(StartupRow, startup_id)
        return _startup_from_row(row) if row else None


class SqlAlchemyStartupDocumentRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, document: StartupDocument) -> StartupDocument:
        async with self._sessions.begin() as session:
            session.add(StartupDocumentRow(**_startup_document_values(document)))
        return document

    async def list_for_startup(self, startup_id: UUID) -> list[StartupDocument]:
        statement = select(StartupDocumentRow).where(StartupDocumentRow.startup_id == startup_id)
        async with self._sessions() as session:
            rows = (await session.scalars(statement)).all()
        return [_startup_document_from_row(row) for row in rows]


class SqlAlchemyAnalysisRunRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, run: AnalysisRun) -> AnalysisRun:
        async with self._sessions.begin() as session:
            session.add(AnalysisRunRow(**_analysis_values(run)))
        return run

    async def get(self, run_id: UUID) -> AnalysisRun | None:
        async with self._sessions() as session:
            row = await session.get(AnalysisRunRow, run_id)
        return _analysis_from_row(row) if row else None


class SqlAlchemyKnowledgeDocumentRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, document: KnowledgeDocument) -> KnowledgeDocument:
        async with self._sessions.begin() as session:
            session.add(KnowledgeDocumentRow(**_knowledge_document_values(document)))
        return document

    async def get(self, document_id: UUID) -> KnowledgeDocument | None:
        async with self._sessions() as session:
            row = await session.get(KnowledgeDocumentRow, document_id)
        return _knowledge_document_from_row(row) if row else None


class SqlAlchemyKnowledgeChunkRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, chunk: KnowledgeChunk) -> KnowledgeChunk:
        async with self._sessions.begin() as session:
            session.add(KnowledgeChunkRow(**_knowledge_chunk_values(chunk)))
        return chunk

    async def get(self, chunk_id: UUID) -> KnowledgeChunk | None:
        async with self._sessions() as session:
            row = await session.get(KnowledgeChunkRow, chunk_id)
        return _knowledge_chunk_from_row(row) if row else None

    async def list_for_document(self, document_id: UUID) -> list[KnowledgeChunk]:
        statement = (
            select(KnowledgeChunkRow)
            .where(KnowledgeChunkRow.document_id == document_id)
            .order_by(KnowledgeChunkRow.chunk_index)
        )
        async with self._sessions() as session:
            rows = (await session.scalars(statement)).all()
        return [_knowledge_chunk_from_row(row) for row in rows]


def _startup_values(value: Startup) -> dict[str, object]:
    return {
        "id": value.id,
        "name": value.name,
        "website": value.website,
        "sector": value.sector,
        "stage": value.stage,
        "location": value.location,
        "short_description": value.short_description,
        "founded_year": value.founded_year,
        "team_size": value.team_size,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }


def _startup_from_row(row: StartupRow) -> Startup:
    return Startup(
        id=row.id,
        name=row.name,
        website=row.website,
        sector=row.sector,
        stage=row.stage,
        location=row.location,
        short_description=row.short_description,
        founded_year=row.founded_year,
        team_size=row.team_size,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _startup_document_values(value: StartupDocument) -> dict[str, object]:
    return {
        "id": value.id,
        "startup_id": value.startup_id,
        "document_type": value.document_type,
        "title": value.title,
        "content_text": value.content_text,
        "source_url": value.source_url,
        "published_at": value.published_at,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }


def _startup_document_from_row(row: StartupDocumentRow) -> StartupDocument:
    return StartupDocument(
        id=row.id,
        startup_id=row.startup_id,
        document_type=row.document_type,
        title=row.title,
        content_text=row.content_text,
        source_url=row.source_url,
        published_at=row.published_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _analysis_values(value: AnalysisRun) -> dict[str, object]:
    return {
        "id": value.id,
        "query": value.query,
        "status": value.status.value,
        "started_at": value.started_at,
        "finished_at": value.finished_at,
        "error_code": value.error_code,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }


def _analysis_from_row(row: AnalysisRunRow) -> AnalysisRun:
    return AnalysisRun(
        id=row.id,
        query=row.query,
        status=AnalysisStatus(row.status),
        started_at=row.started_at,
        finished_at=row.finished_at,
        error_code=row.error_code,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _knowledge_document_values(value: KnowledgeDocument) -> dict[str, object]:
    return {
        "id": value.id,
        "title": value.title,
        "source_url": value.source_url,
        "content_type": value.content_type,
        "published_at": value.published_at,
        "content_hash": value.content_hash,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }


def _knowledge_document_from_row(row: KnowledgeDocumentRow) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=row.id,
        title=row.title,
        source_url=row.source_url,
        content_type=row.content_type,
        published_at=row.published_at,
        content_hash=row.content_hash,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _knowledge_chunk_values(value: KnowledgeChunk) -> dict[str, object]:
    return {
        "id": value.id,
        "document_id": value.document_id,
        "content": value.content,
        "chunk_index": value.chunk_index,
        "metadata_json": value.metadata,
        "content_hash": value.content_hash,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }


def _knowledge_chunk_from_row(row: KnowledgeChunkRow) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=row.id,
        document_id=row.document_id,
        content=row.content,
        chunk_index=row.chunk_index,
        metadata=row.metadata_json,
        content_hash=row.content_hash,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
