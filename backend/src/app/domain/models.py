from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AIMaturity(StrEnum):
    NON_AI = "non-ai"
    AI_ENABLED = "ai-enabled"
    AI_NATIVE = "ai-native"


@dataclass(frozen=True, slots=True)
class SourceReference:
    source_id: UUID
    source_url: str
    title: str
    excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class Evidence:
    claim: str
    sources: tuple[SourceReference, ...]
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError("Uma evidência precisa referenciar ao menos uma fonte.")


@dataclass(frozen=True, slots=True)
class Citation:
    source_id: UUID
    source_url: str
    label: str


@dataclass(frozen=True, slots=True)
class TechnicalGap:
    name: str
    description: str
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class Recommendation:
    technology: str
    technical_reason: str
    business_reason: str
    priority: str
    implementation_complexity: str
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True, slots=True)
class RecoverableError:
    code: str
    message: str
    node: str | None = None


@dataclass(slots=True)
class Startup:
    name: str
    website: str | None = None
    sector: str | None = None
    stage: str | None = None
    location: str | None = None
    short_description: str | None = None
    founded_year: int | None = None
    team_size: int | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class StartupDocument:
    startup_id: UUID
    document_type: str
    title: str
    content_text: str
    source_url: str
    published_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class AnalysisRun:
    query: str
    status: AnalysisStatus = AnalysisStatus.PENDING
    id: UUID = field(default_factory=uuid4)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class KnowledgeDocument:
    title: str
    source_url: str
    content_type: str
    content_hash: str
    published_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class KnowledgeChunk:
    document_id: UUID
    content: str
    chunk_index: int
    content_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
