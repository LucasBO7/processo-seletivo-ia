from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from app.application.contracts.classification import StartupClassification
from app.application.contracts.evidence_validation import (
    ClaimValidation,
    ClassificationValidation,
    ValidatedClassification,
    ValidatedStartupProfile,
)
from app.application.contracts.extraction import StructuredStartupProfile
from app.application.contracts.nvidia_rag import NvidiaStartupContext
from app.application.contracts.query_plan import QueryPlan
from app.application.contracts.recommendation import StartupRecommendation
from app.domain.models import (
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
    validated_profiles: list[ValidatedStartupProfile]
    validated_classifications: list[ValidatedClassification]
    claim_validations: list[ClaimValidation]
    classification_validations: list[ClassificationValidation]
    validated_claims: list[ClaimValidation]
    rejected_claims: list[ClaimValidation]
    conflicting_claims: list[ClaimValidation]
    evidence_gaps: list[ClaimValidation]
    technical_gaps: list[TechnicalGap]
    retrieval_query: str
    candidate_chunks: list[RetrievedChunk]
    reranked_chunks: list[RetrievedChunk]
    nvidia_contexts: list[NvidiaStartupContext]
    recommendations: list[StartupRecommendation]
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
        validated_profiles=[],
        validated_classifications=[],
        claim_validations=[],
        classification_validations=[],
        validated_claims=[],
        rejected_claims=[],
        conflicting_claims=[],
        evidence_gaps=[],
        technical_gaps=[],
        candidate_chunks=[],
        reranked_chunks=[],
        nvidia_contexts=[],
        recommendations=[],
        warnings=[],
        errors=[],
        metrics={},
    )
