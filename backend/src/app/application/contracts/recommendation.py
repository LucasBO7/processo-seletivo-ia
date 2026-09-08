from __future__ import annotations

import re
from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.contracts.extraction import ProfileField
from app.application.contracts.knowledge_ingestion import NvidiaTechnology
from app.application.contracts.nvidia_rag import NvidiaRetrievalScores
from app.domain.models import AIMaturity


class StrictRecommendationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecommendationPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImplementationComplexity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationNeedKind(StrEnum):
    VALIDATED_TECHNICAL_NEED = "validated_technical_need"
    VALIDATED_TECHNICAL_GAP = "validated_technical_gap"


class NeedCriticality(StrEnum):
    BLOCKER = "blocker"
    IMPORTANT = "important"
    OPTIMIZATION = "optimization"


class BusinessRelevance(StrEnum):
    CORE = "core"
    SUPPORTING = "supporting"


class EvidenceStrength(StrEnum):
    CORROBORATED = "corroborated"
    SINGLE_SOURCE = "single_source"


class IntegrationScope(StrEnum):
    CONFIGURATION_OR_API = "configuration_or_api"
    SINGLE_COMPONENT = "single_component"
    PLATFORM_OR_MIGRATION = "platform_or_migration"


class InfrastructureChange(StrEnum):
    NONE = "none"
    MODERATE = "moderate"
    MAJOR = "major"


class SpecializedSkills(StrEnum):
    STANDARD = "standard"
    SPECIALIZED = "specialized"
    ADVANCED = "advanced"


def _unique(values: list[object]) -> list[object]:
    return list(dict.fromkeys(values))


class RecommendationNeed(StrictRecommendationContract):
    key: str = Field(pattern=r"^need:[0-9]+$", max_length=40)
    kind: RecommendationNeedKind
    description: str = Field(min_length=1, max_length=4_000)
    startup_evidence_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @field_validator("startup_evidence_ids")
    @classmethod
    def deduplicate_evidence(cls, values: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(values))


class RecommendationCandidate(StrictRecommendationContract):
    technology: NvidiaTechnology
    need_keys: list[str] = Field(min_length=1, max_length=50)
    technical_justification: str = Field(min_length=1, max_length=4_000)
    business_justification: str = Field(min_length=1, max_length=4_000)
    next_action: str = Field(min_length=1, max_length=2_000)
    startup_evidence_ids: list[UUID] = Field(min_length=1, max_length=100)
    nvidia_chunk_ids: list[UUID] = Field(min_length=1, max_length=100)
    need_criticality: NeedCriticality
    business_relevance: BusinessRelevance
    priority: RecommendationPriority
    priority_evidence_ids: list[UUID] = Field(min_length=1, max_length=100)
    integration_scope: IntegrationScope
    infrastructure_change: InfrastructureChange
    specialized_skills: SpecializedSkills
    implementation_complexity: ImplementationComplexity
    complexity_nvidia_chunk_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("technical_justification", "business_justification", "next_action")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("recommendation text must not be empty")
        return normalized

    @field_validator(
        "need_keys",
        "startup_evidence_ids",
        "nvidia_chunk_ids",
        "priority_evidence_ids",
        "complexity_nvidia_chunk_ids",
    )
    @classmethod
    def deduplicate_lists(cls, values: list[object]) -> list[object]:
        return _unique(values)


class RecommendationCandidateBatch(StrictRecommendationContract):
    candidates: list[RecommendationCandidate] = Field(default_factory=list, max_length=100)


class PriorityBasis(StrictRecommendationContract):
    need_criticality: NeedCriticality
    business_relevance: BusinessRelevance
    evidence_strength: EvidenceStrength
    priority_score: int = Field(ge=0, le=4)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=100)


class ComplexityBasis(StrictRecommendationContract):
    integration_scope: IntegrationScope
    infrastructure_change: InfrastructureChange
    specialized_skills: SpecializedSkills
    complexity_score: int = Field(ge=0, le=6)
    nvidia_chunk_ids: list[UUID] = Field(min_length=1, max_length=100)


class StartupRecommendationEvidence(StrictRecommendationContract):
    startup_id: UUID
    source_id: UUID
    source_url: str = Field(min_length=1, max_length=2_048)
    field: ProfileField
    value: str = Field(min_length=1, max_length=4_000)

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTP URL")
        return value


class NvidiaRecommendationEvidence(StrictRecommendationContract):
    chunk_id: UUID
    document_id: UUID
    title: str = Field(min_length=1, max_length=500)
    technology: NvidiaTechnology
    source_url: str = Field(min_length=1, max_length=2_048)
    source_section: str | None = Field(default=None, max_length=500)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    retrieval_scores: NvidiaRetrievalScores

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("NVIDIA source_url must be HTTPS")
        return value

    @model_validator(mode="after")
    def validate_locator(self) -> Self:
        if self.source_section is None and self.start_offset is None and self.end_offset is None:
            raise ValueError("NVIDIA evidence requires a locator")
        return self


class StartupRecommendation(StrictRecommendationContract):
    startup_id: UUID
    startup_name: str = Field(min_length=1, max_length=255)
    maturity_considered: AIMaturity | None
    technology: NvidiaTechnology
    need_keys: list[str] = Field(min_length=1, max_length=50)
    technical_justification: str = Field(min_length=1, max_length=4_000)
    business_justification: str = Field(min_length=1, max_length=4_000)
    priority: RecommendationPriority
    priority_basis: PriorityBasis
    implementation_complexity: ImplementationComplexity
    complexity_basis: ComplexityBasis
    next_action: str = Field(min_length=1, max_length=2_000)
    startup_evidence: list[StartupRecommendationEvidence] = Field(min_length=1, max_length=100)
    nvidia_evidence: list[NvidiaRecommendationEvidence] = Field(min_length=1, max_length=100)
