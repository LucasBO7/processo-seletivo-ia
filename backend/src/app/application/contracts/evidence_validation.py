from __future__ import annotations

import re
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.contracts.classification import StartupClassification
from app.application.contracts.extraction import (
    ExtractionSource,
    ProfileField,
    StructuredStartupProfile,
)
from app.domain.models import AIMaturity

MAX_ASSESSMENTS = 500
MAX_JUSTIFICATION_LENGTH = 4_000


class StrictEvidenceValidationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"


class SourceVerdict(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NOT_FOUND = "not_found"


class SourceAssessment(StrictEvidenceValidationContract):
    startup_id: UUID
    source_id: UUID
    source_url: str
    verdict: SourceVerdict


class ClaimAssessmentOutput(StrictEvidenceValidationContract):
    claim_key: str = Field(min_length=1, max_length=200)
    status: EvidenceStatus
    justification: str = Field(min_length=1, max_length=MAX_JUSTIFICATION_LENGTH)
    analyzed_sources: list[SourceAssessment] = Field(
        default_factory=list, max_length=MAX_ASSESSMENTS
    )

    @field_validator("claim_key", "justification")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("validation text must not be empty")
        return normalized

    @field_validator("analyzed_sources")
    @classmethod
    def deduplicate_sources(cls, sources: list[SourceAssessment]) -> list[SourceAssessment]:
        result: list[SourceAssessment] = []
        seen: set[tuple[UUID, UUID, str]] = set()
        for source in sources:
            key = (source.startup_id, source.source_id, source.source_url)
            if key not in seen:
                seen.add(key)
                result.append(source)
        return result

    @model_validator(mode="after")
    def validate_status_coherence(self) -> Self:
        verdicts = {source.verdict for source in self.analyzed_sources}
        supports = SourceVerdict.SUPPORTS in verdicts
        contradicts = SourceVerdict.CONTRADICTS in verdicts
        if self.status is EvidenceStatus.SUPPORTED and (not supports or contradicts):
            raise ValueError("supported requires support without contradiction")
        if self.status is EvidenceStatus.CONFLICTING and not (supports and contradicts):
            raise ValueError("conflicting requires support and contradiction")
        if self.status is EvidenceStatus.UNSUPPORTED and (supports or not self.analyzed_sources):
            raise ValueError("unsupported requires analyzed evidence without support")
        if self.status is EvidenceStatus.INSUFFICIENT and (supports or contradicts):
            raise ValueError("insufficient cannot contain decisive source verdicts")
        return self


class ValidatorOutput(StrictEvidenceValidationContract):
    assessments: list[ClaimAssessmentOutput] = Field(min_length=1, max_length=MAX_ASSESSMENTS)


class ClaimValidation(ClaimAssessmentOutput):
    startup_id: UUID
    field: ProfileField
    value: str = Field(min_length=1, max_length=4_000)
    original_sources: list[ExtractionSource] = Field(min_length=1, max_length=MAX_ASSESSMENTS)


class ClassificationValidation(ClaimAssessmentOutput):
    startup_id: UUID
    category: AIMaturity | None


class ValidatedStartupProfile(StructuredStartupProfile):
    pass


class ValidatedClassification(StartupClassification):
    pass
