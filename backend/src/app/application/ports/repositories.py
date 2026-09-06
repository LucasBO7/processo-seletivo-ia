from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models import (
    AnalysisRun,
    KnowledgeChunk,
    KnowledgeDocument,
    Startup,
    StartupDocument,
)


class StartupRepository(Protocol):
    async def add(self, startup: Startup) -> Startup: ...

    async def get(self, startup_id: UUID) -> Startup | None: ...


class StartupDocumentRepository(Protocol):
    async def add(self, document: StartupDocument) -> StartupDocument: ...

    async def list_for_startup(self, startup_id: UUID) -> list[StartupDocument]: ...


class AnalysisRunRepository(Protocol):
    async def add(self, run: AnalysisRun) -> AnalysisRun: ...

    async def get(self, run_id: UUID) -> AnalysisRun | None: ...


class KnowledgeDocumentRepository(Protocol):
    async def add(self, document: KnowledgeDocument) -> KnowledgeDocument: ...

    async def get(self, document_id: UUID) -> KnowledgeDocument | None: ...


class KnowledgeChunkRepository(Protocol):
    async def add(self, chunk: KnowledgeChunk) -> KnowledgeChunk: ...

    async def get(self, chunk_id: UUID) -> KnowledgeChunk | None: ...

    async def list_for_document(self, document_id: UUID) -> list[KnowledgeChunk]: ...
