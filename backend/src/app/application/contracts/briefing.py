from __future__ import annotations

import re
from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.contracts.classification import ClassificationSignalType
from app.application.contracts.extraction import ProfileField
from app.application.contracts.knowledge_ingestion import NvidiaTechnology
from app.application.contracts.nvidia_rag import NvidiaRetrievalScores
from app.application.contracts.recommendation import (
    ImplementationComplexity,
    RecommendationPriority,
)
from app.domain.models import AIMaturity


class StrictBriefingContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BriefingStatementKind(StrEnum):
    CONFIRMED_FACT = "confirmed_fact"
    SUPPORTED_INFERENCE = "supported_inference"
    UNCERTAINTY = "uncertainty"
    GAP = "gap"


class BriefingMissingSection(StrEnum):
    PROFILE = "profile"
    BUSINESS = "business"
    AI_MATURITY = "ai_maturity"
    SIGNALS = "signals"
    STACK = "stack"
    TECHNICAL_GAPS = "technical_gaps"
    INCEPTION_OPPORTUNITIES = "inception_opportunities"


class BriefingStatementCandidate(StrictBriefingContract):
    kind: BriefingStatementKind
    text: str = Field(min_length=1, max_length=4_000)
    citation_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("statement must not be empty")
        return normalized

    @field_validator("citation_ids")
    @classmethod
    def validate_citation_ids(cls, values: list[str]) -> list[str]:
        unique = list(dict.fromkeys(values))
        if any(not re.fullmatch(r"[SN][1-9][0-9]*", value) for value in unique):
            raise ValueError("invalid citation id")
        return unique


class BriefingNarrativeOutput(StrictBriefingContract):
    executive_summary: list[BriefingStatementCandidate] = Field(min_length=1, max_length=100)
    inception_opportunities: list[BriefingStatementCandidate] = Field(
        default_factory=list, max_length=100
    )
    uncertainties_and_gaps: list[BriefingStatementCandidate] = Field(
        default_factory=list, max_length=100
    )


class BriefingStatement(BriefingStatementCandidate):
    pass


class BriefingStartupCitation(StrictBriefingContract):
    citation_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    startup_id: UUID
    source_id: UUID
    source_url: str = Field(min_length=1, max_length=2_048)
    fields: list[ProfileField] = Field(default_factory=list, max_length=len(ProfileField))
    values: list[str] = Field(min_length=1, max_length=100)

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("startup citation URL must be absolute")
        return value

    @field_validator("fields", "values")
    @classmethod
    def deduplicate_lists(cls, values: list[object]) -> list[object]:
        return list(dict.fromkeys(values))


class BriefingNvidiaCitation(StrictBriefingContract):
    citation_id: str = Field(pattern=r"^N[1-9][0-9]*$")
    chunk_id: UUID
    document_id: UUID
    technology: NvidiaTechnology
    title: str = Field(min_length=1, max_length=500)
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
            raise ValueError("NVIDIA citation URL must be HTTPS")
        return value

    @model_validator(mode="after")
    def validate_locator(self) -> Self:
        if self.source_section is None and self.start_offset is None and self.end_offset is None:
            raise ValueError("NVIDIA citation requires a locator")
        return self


class BriefingFact(StrictBriefingContract):
    field: ProfileField
    value: str = Field(min_length=1, max_length=4_000)
    citation_ids: list[str] = Field(min_length=1, max_length=100)


class BriefingClassificationSignal(StrictBriefingContract):
    type: ClassificationSignalType
    description: str = Field(min_length=1, max_length=2_000)
    citation_ids: list[str] = Field(min_length=1, max_length=100)


class BriefingTechnicalGap(StrictBriefingContract):
    name: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=4_000)
    citation_ids: list[str] = Field(min_length=1, max_length=100)


class BriefingRecommendation(StrictBriefingContract):
    technology: NvidiaTechnology
    need_keys: list[str] = Field(min_length=1, max_length=50)
    technical_justification: str = Field(min_length=1, max_length=4_000)
    business_justification: str = Field(min_length=1, max_length=4_000)
    priority: RecommendationPriority
    implementation_complexity: ImplementationComplexity
    next_action: str = Field(min_length=1, max_length=2_000)
    startup_citation_ids: list[str] = Field(min_length=1, max_length=100)
    nvidia_citation_ids: list[str] = Field(min_length=1, max_length=100)
    priority_citation_ids: list[str] = Field(min_length=1, max_length=100)
    complexity_citation_ids: list[str] = Field(min_length=1, max_length=100)


class StartupBriefing(StrictBriefingContract):
    startup_id: UUID
    startup_name: str = Field(min_length=1, max_length=255)
    business_facts: list[BriefingFact] = Field(default_factory=list, max_length=100)
    ai_maturity: AIMaturity | None
    ai_maturity_citation_ids: list[str] = Field(default_factory=list, max_length=100)
    classification_signals: list[BriefingClassificationSignal] = Field(
        default_factory=list, max_length=100
    )
    identified_stack: list[BriefingFact] = Field(default_factory=list, max_length=100)
    technical_gaps: list[BriefingTechnicalGap] = Field(default_factory=list, max_length=100)
    recommendations: list[BriefingRecommendation] = Field(min_length=1, max_length=100)
    executive_summary: list[BriefingStatement] = Field(min_length=1, max_length=100)
    inception_opportunities: list[BriefingStatement] = Field(default_factory=list, max_length=100)
    uncertainties_and_gaps: list[BriefingStatement] = Field(default_factory=list, max_length=100)
    startup_citations: list[BriefingStartupCitation] = Field(min_length=1, max_length=100)
    nvidia_citations: list[BriefingNvidiaCitation] = Field(min_length=1, max_length=100)
    missing_sections: list[BriefingMissingSection] = Field(default_factory=list)
    markdown: str = Field(min_length=1, max_length=200_000)

    @model_validator(mode="after")
    def validate_maturity_citations(self) -> Self:
        if self.ai_maturity is not None and not self.ai_maturity_citation_ids:
            raise ValueError("AI maturity requires citations")
        if self.ai_maturity is None and self.ai_maturity_citation_ids:
            raise ValueError("missing AI maturity cannot have citations")
        return self
