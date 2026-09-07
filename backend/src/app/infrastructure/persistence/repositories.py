from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, case, false, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from app.application.contracts.retrieval import RankedStartup, StartupSearchCriteria
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

    async def search(self, criteria: StartupSearchCriteria, *, limit: int) -> list[RankedStartup]:
        conditions: list[ColumnElement[bool]] = []
        if criteria.sectors:
            conditions.append(func.lower(StartupRow.sector).in_(criteria.sectors))
        if criteria.stages:
            conditions.append(func.lower(StartupRow.stage).in_(criteria.stages))
        if criteria.locations:
            conditions.append(func.lower(StartupRow.location).in_(criteria.locations))
        if criteria.requires_team_size_match:
            size_conditions = [
                and_(
                    StartupRow.team_size >= item.minimum,
                    true_if_unbounded_or_maximum(item.maximum),
                )
                for item in criteria.team_size_ranges
            ]
            conditions.append(or_(*size_conditions) if size_conditions else false())

        score: ColumnElement[float] = literal(float(criteria.structured_filter_count))
        text_matches: list[ColumnElement[bool]] = []
        for term in criteria.text_terms:
            startup_match = or_(
                func.lower(func.coalesce(StartupRow.name, "")).contains(term),
                func.lower(func.coalesce(StartupRow.sector, "")).contains(term),
                func.lower(func.coalesce(StartupRow.stage, "")).contains(term),
                func.lower(func.coalesce(StartupRow.location, "")).contains(term),
                func.lower(func.coalesce(StartupRow.short_description, "")).contains(term),
            )
            document_match = (
                select(StartupDocumentRow.id)
                .where(
                    StartupDocumentRow.startup_id == StartupRow.id,
                    or_(
                        func.lower(StartupDocumentRow.title).contains(term),
                        func.lower(StartupDocumentRow.content_text).contains(term),
                    ),
                )
                .exists()
            )
            text_match = or_(startup_match, document_match)
            text_matches.append(text_match)
            score += case((text_match, 1.0), else_=0.0)
        if text_matches:
            conditions.append(or_(*text_matches))

        statement = (
            select(StartupRow, score.label("relevance_score"))
            .where(*conditions)
            .order_by(score.desc(), func.lower(StartupRow.name), StartupRow.id)
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = (await session.execute(statement)).all()
        return [
            RankedStartup(startup=_startup_from_row(row), score=float(relevance_score))
            for row, relevance_score in rows
        ]


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

    async def list_for_startups(self, startup_ids: list[UUID]) -> list[StartupDocument]:
        if not startup_ids:
            return []
        statement = (
            select(StartupDocumentRow)
            .where(StartupDocumentRow.startup_id.in_(startup_ids))
            .order_by(
                StartupDocumentRow.startup_id,
                StartupDocumentRow.published_at.desc().nullslast(),
                func.lower(StartupDocumentRow.title),
                StartupDocumentRow.id,
            )
        )
        async with self._sessions() as session:
            rows = (await session.scalars(statement)).all()
        return [_startup_document_from_row(row) for row in rows]


def true_if_unbounded_or_maximum(maximum: int | None) -> ColumnElement[bool]:
    if maximum is None:
        return literal(True)
    return StartupRow.team_size <= maximum


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
        document.source_key = document.source_key or f"legacy-{document.id}"
        document.technology = document.technology or "unknown"
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
        "source_key": value.source_key or f"legacy-{value.id}",
        "technology": value.technology or "unknown",
        "revision": value.revision,
        "pipeline_version": value.pipeline_version,
        "ingested_at": value.ingested_at,
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
        source_key=row.source_key,
        technology=row.technology,
        revision=row.revision,
        pipeline_version=row.pipeline_version,
        ingested_at=row.ingested_at,
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
