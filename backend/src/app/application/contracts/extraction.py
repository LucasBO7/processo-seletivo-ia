from __future__ import annotations

import re
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_FACT_LENGTH = 4_000
MAX_PROFILE_ITEMS = 50


class StrictExtractionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProfileField(StrEnum):
    PRODUCT = "product"
    BUSINESS_MODEL = "business_model"
    SECTOR = "sector"
    TARGET_AUDIENCE = "target_audience"
    AI_USE_CASES = "ai_use_cases"
    TECHNOLOGIES = "technologies"
    INFRASTRUCTURE = "infrastructure"
    EXTERNAL_DEPENDENCIES = "external_dependencies"
    TECHNICAL_NEEDS = "technical_needs"
    CLAIMS = "claims"


class ExtractionSource(StrictExtractionContract):
    startup_id: UUID
    source_id: UUID
    source_url: str = Field(min_length=1)


class ExtractedFact(StrictExtractionContract):
    value: str = Field(min_length=1, max_length=MAX_FACT_LENGTH)
    sources: list[ExtractionSource] = Field(min_length=1, max_length=MAX_PROFILE_ITEMS)

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("fact value must not be empty")
        return normalized

    @field_validator("sources")
    @classmethod
    def deduplicate_sources(cls, sources: list[ExtractionSource]) -> list[ExtractionSource]:
        result: list[ExtractionSource] = []
        seen: set[tuple[UUID, UUID, str]] = set()
        for source in sources:
            key = (source.startup_id, source.source_id, source.source_url)
            if key not in seen:
                seen.add(key)
                result.append(source)
        return result


class ExtractorOutput(StrictExtractionContract):
    product: ExtractedFact | None = None
    business_model: ExtractedFact | None = None
    sector: ExtractedFact | None = None
    target_audience: ExtractedFact | None = None
    ai_use_cases: list[ExtractedFact] = Field(default_factory=list, max_length=MAX_PROFILE_ITEMS)
    technologies: list[ExtractedFact] = Field(default_factory=list, max_length=MAX_PROFILE_ITEMS)
    infrastructure: list[ExtractedFact] = Field(default_factory=list, max_length=MAX_PROFILE_ITEMS)
    external_dependencies: list[ExtractedFact] = Field(
        default_factory=list, max_length=MAX_PROFILE_ITEMS
    )
    technical_needs: list[ExtractedFact] = Field(default_factory=list, max_length=MAX_PROFILE_ITEMS)
    claims: list[ExtractedFact] = Field(default_factory=list, max_length=MAX_PROFILE_ITEMS)
    unknown_fields: list[ProfileField] = Field(default_factory=list, max_length=len(ProfileField))

    @field_validator(
        "ai_use_cases",
        "technologies",
        "infrastructure",
        "external_dependencies",
        "technical_needs",
        "claims",
    )
    @classmethod
    def deduplicate_facts(cls, facts: list[ExtractedFact]) -> list[ExtractedFact]:
        result: list[ExtractedFact] = []
        seen: set[str] = set()
        for fact in facts:
            key = fact.value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(fact)
        return result

    @field_validator("unknown_fields")
    @classmethod
    def deduplicate_unknown_fields(cls, fields: list[ProfileField]) -> list[ProfileField]:
        return list(dict.fromkeys(fields))

    @model_validator(mode="after")
    def validate_unknown_fields(self) -> Self:
        expected = {
            field
            for field in ProfileField
            if getattr(self, field.value) is None or getattr(self, field.value) == []
        }
        if set(self.unknown_fields) != expected:
            raise ValueError("unknown fields must match fields without extracted facts")
        return self


class StructuredStartupProfile(ExtractorOutput):
    startup_id: UUID
    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, name: str) -> str:
        normalized = re.sub(r"\s+", " ", name).strip()
        if not normalized:
            raise ValueError("startup name must not be empty")
        return normalized
