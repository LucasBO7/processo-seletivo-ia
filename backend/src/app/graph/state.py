from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from app.application.contracts.classification import StartupClassification
from app.application.contracts.extraction import StructuredStartupProfile
from app.application.contracts.query_plan import QueryPlan
from app.domain.models import (
    Evidence,
    Recommendation,
    RecoverableError,
    SourceReference,
    TechnicalGap,
)


class CandidateStartup(TypedDict):
    startup_id: UUID
    name: str
    score: float | None


class RetrievedChunk(TypedDict):
    chunk_id: UUID
    document_id: UUID
    content: str
    source_url: str
    score: float


class AppState(TypedDict, total=False):
    run_id: UUID
    correlation_id: str
    query: str
    query_plan: QueryPlan
    filters: dict[str, Any]
    candidate_startups: list[CandidateStartup]
    selected_sources: list[SourceReference]
    structured_profiles: list[StructuredStartupProfile]
    classifications: list[StartupClassification]
    validated_claims: list[Evidence]
    rejected_claims: list[Evidence]
    technical_gaps: list[TechnicalGap]
    retrieval_query: str
    candidate_chunks: list[RetrievedChunk]
    reranked_chunks: list[RetrievedChunk]
    recommendations: list[Recommendation]
    briefing: str
    warnings: list[str]
    errors: list[RecoverableError]
    metrics: dict[str, float]


def empty_state(*, run_id: UUID, correlation_id: str, query: str) -> AppState:
    return AppState(
        run_id=run_id,
        correlation_id=correlation_id,
        query=query,
        filters={},
        candidate_startups=[],
        selected_sources=[],
        structured_profiles=[],
        classifications=[],
        validated_claims=[],
        rejected_claims=[],
        technical_gaps=[],
        candidate_chunks=[],
        reranked_chunks=[],
        recommendations=[],
        warnings=[],
        errors=[],
        metrics={},
    )
