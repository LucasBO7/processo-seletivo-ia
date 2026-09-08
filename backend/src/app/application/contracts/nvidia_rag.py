from __future__ import annotations

import math
import re
from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.contracts.knowledge_ingestion import NvidiaTechnology


class StrictNvidiaRagContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NvidiaContextStatus(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class NvidiaRankingMode(StrEnum):
    RERANKER = "reranker"
    HYBRID_FALLBACK = "hybrid_fallback"


class NvidiaQueryTrace(StrictNvidiaRagContract):
    attempt: int = Field(ge=1, le=3)
    text: str = Field(min_length=1, max_length=2_000)
    fields: list[str] = Field(default_factory=list, max_length=20)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("query must not be empty")
        return normalized

    @field_validator("fields")
    @classmethod
    def deduplicate_fields(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @field_validator("evidence_ids")
    @classmethod
    def deduplicate_evidence(cls, values: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(values))


class NvidiaRetrievalScores(StrictNvidiaRagContract):
    vector_raw_score: float | None = None
    vector_rank: int | None = Field(default=None, ge=1)
    vector_rank_score: float | None = Field(default=None, ge=0, le=1)
    bm25_raw_score: float | None = None
    bm25_rank: int | None = Field(default=None, ge=1)
    bm25_rank_score: float | None = Field(default=None, ge=0, le=1)
    vector_weight: float = Field(ge=0, le=1)
    lexical_weight: float = Field(ge=0, le=1)
    hybrid_score: float = Field(ge=0, le=1)
    reranker_score: float | None = Field(default=None, ge=0, le=1)
    reranker_rank: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_finite_scores(self) -> Self:
        for field_name in (
            "vector_raw_score",
            "vector_rank_score",
            "bm25_raw_score",
            "bm25_rank_score",
            "vector_weight",
            "lexical_weight",
            "hybrid_score",
            "reranker_score",
        ):
            value = getattr(self, field_name)
            if value is not None and not math.isfinite(value):
                raise ValueError("scores must be finite")
        return self


class NvidiaRetrievedChunk(StrictNvidiaRagContract):
    startup_id: UUID
    chunk_id: UUID
    document_id: UUID
    content: str = Field(min_length=1, max_length=20_000)
    title: str = Field(min_length=1, max_length=500)
    technology: NvidiaTechnology
    source_key: str = Field(min_length=1, max_length=120)
    source_url: str = Field(min_length=1, max_length=2_048)
    chunk_index: int = Field(ge=0)
    source_section: str | None = Field(default=None, max_length=500)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    retrieval_attempts: list[int] = Field(min_length=1, max_length=3)
    matched_queries: list[str] = Field(min_length=1, max_length=3)
    scores: NvidiaRetrievalScores

    @field_validator("title", "source_key")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("required text must not be empty")
        return normalized

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be empty")
        return value

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("source_url must be an official HTTPS URL")
        return normalized

    @field_validator("retrieval_attempts")
    @classmethod
    def normalize_attempts(cls, values: list[int]) -> list[int]:
        return sorted(set(values))

    @field_validator("matched_queries")
    @classmethod
    def normalize_queries(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(re.sub(r"\s+", " ", item).strip() for item in values))

    @model_validator(mode="after")
    def validate_locator_and_offsets(self) -> Self:
        if not self.source_section and self.start_offset is None and self.end_offset is None:
            raise ValueError("a citation locator is required")
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset < self.start_offset
        ):
            raise ValueError("end_offset must not precede start_offset")
        return self


class NvidiaContextSufficiency(StrictNvidiaRagContract):
    status: NvidiaContextStatus
    relevant_chunk_count: int = Field(ge=0)
    distinct_document_count: int = Field(ge=0)
    best_score: float | None = Field(default=None, ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    ranking_mode: NvidiaRankingMode
    reasons: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is NvidiaContextStatus.SUFFICIENT and self.reasons:
            raise ValueError("sufficient context cannot contain insufficiency reasons")
        if self.status is NvidiaContextStatus.INSUFFICIENT and not self.reasons:
            raise ValueError("insufficient context requires reasons")
        return self


class NvidiaContextGap(StrictNvidiaRagContract):
    code: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=500)


class NvidiaStartupContext(StrictNvidiaRagContract):
    startup_id: UUID
    startup_name: str = Field(min_length=1, max_length=255)
    attempted_queries: list[str] = Field(min_length=1, max_length=3)
    query_traces: list[NvidiaQueryTrace] = Field(min_length=1, max_length=3)
    attempts: int = Field(ge=1, le=3)
    chunks: list[NvidiaRetrievedChunk] = Field(default_factory=list, max_length=100)
    sufficiency: NvidiaContextSufficiency
    gaps: list[NvidiaContextGap] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_attempts(self) -> Self:
        if self.attempts != len(self.attempted_queries) or self.attempts != len(self.query_traces):
            raise ValueError("attempt count must match query traces")
        if self.sufficiency.status is NvidiaContextStatus.SUFFICIENT and self.gaps:
            raise ValueError("sufficient context cannot contain gaps")
        return self
