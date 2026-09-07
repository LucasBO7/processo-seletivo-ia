from __future__ import annotations

import re
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.contracts.extraction import ExtractionSource
from app.domain.models import AIMaturity

MAX_JUSTIFICATION_LENGTH = 4_000
MAX_SIGNAL_DESCRIPTION_LENGTH = 2_000
MAX_SIGNALS = 50


class StrictClassificationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClassificationStatus(StrEnum):
    CLASSIFIED = "classified"
    UNCERTAIN = "uncertain"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClassificationSignalType(StrEnum):
    CORE_AI_DEPENDENCY = "core_ai_dependency"
    SUPPORTING_AI_USE = "supporting_ai_use"
    EXPLICIT_NON_AI = "explicit_non_ai"
    GENERIC_AI_MENTION = "generic_ai_mention"
    FUTURE_AI_INTENT = "future_ai_intent"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class ClassificationSignal(StrictClassificationContract):
    type: ClassificationSignalType
    description: str = Field(min_length=1, max_length=MAX_SIGNAL_DESCRIPTION_LENGTH)
    sources: list[ExtractionSource] = Field(min_length=1, max_length=MAX_SIGNALS)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("signal description must not be empty")
        return normalized

    @field_validator("sources")
    @classmethod
    def deduplicate_sources(cls, sources: list[ExtractionSource]) -> list[ExtractionSource]:
        return list(
            {
                (source.startup_id, source.source_id, source.source_url): source
                for source in sources
            }.values()
        )


class ClassifierOutput(StrictClassificationContract):
    status: ClassificationStatus
    category: AIMaturity | None
    justification: str = Field(min_length=1, max_length=MAX_JUSTIFICATION_LENGTH)
    confidence: ConfidenceLevel
    signals: list[ClassificationSignal] = Field(default_factory=list, max_length=MAX_SIGNALS)

    @field_validator("justification")
    @classmethod
    def normalize_justification(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("justification must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_classification_coherence(self) -> Self:
        signal_types = {signal.type for signal in self.signals}
        if self.status is ClassificationStatus.UNCERTAIN:
            if self.category is not None or self.confidence is not ConfidenceLevel.LOW:
                raise ValueError("uncertain results require a null category and low confidence")
            return self
        if self.category is None or self.confidence is ConfidenceLevel.LOW:
            raise ValueError("classified results require a category and medium or high confidence")
        required_signal = {
            AIMaturity.AI_NATIVE: ClassificationSignalType.CORE_AI_DEPENDENCY,
            AIMaturity.AI_ENABLED: ClassificationSignalType.SUPPORTING_AI_USE,
            AIMaturity.NON_AI: ClassificationSignalType.EXPLICIT_NON_AI,
        }[self.category]
        if required_signal not in signal_types:
            raise ValueError("the category is not supported by its required signal")
        if ClassificationSignalType.CONFLICTING_EVIDENCE in signal_types:
            raise ValueError("conflicting evidence requires an uncertain result")
        return self


class StartupClassification(ClassifierOutput):
    startup_id: UUID
    name: str = Field(min_length=1)
    evidence_references: list[ExtractionSource] = Field(
        default_factory=list, max_length=MAX_SIGNALS
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, name: str) -> str:
        normalized = re.sub(r"\s+", " ", name).strip()
        if not normalized:
            raise ValueError("startup name must not be empty")
        return normalized
