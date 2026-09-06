from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_LIST_ITEMS = 20
MAX_RATIONALE_LENGTH = 500
MAX_CLARIFICATION_QUESTIONS = 3

NormalizedText = Annotated[str, Field(min_length=1)]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = normalize_text(raw_value)
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


class QueryPlanStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    INVALID = "invalid"


class AnalysisMode(StrEnum):
    TARGETED = "targeted"
    EXPLORATORY = "exploratory"
    COMPARATIVE = "comparative"


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StartupSearchFilters(StrictContract):
    sectors: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    company_sizes: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    stages: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    locations: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    keywords: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    ai_usage_signals: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_lists(cls, value: Any) -> Any:
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return normalize_unique(value)
        return value


class AnalysisStrategy(StrictContract):
    mode: AnalysisMode
    objectives: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_LENGTH)

    @field_validator("objectives", mode="before")
    @classmethod
    def normalize_objectives(cls, value: Any) -> Any:
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return normalize_unique(value)
        return value

    @field_validator("rationale")
    @classmethod
    def normalize_rationale(cls, value: str) -> str:
        value = normalize_text(value)
        if not value:
            raise ValueError("rationale must not be empty")
        return value


class QueryPlan(StrictContract):
    status: QueryPlanStatus
    normalized_query: str = Field(min_length=1, max_length=2_000)
    filters: StartupSearchFilters
    analysis_strategy: AnalysisStrategy
    ambiguities: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    clarification_questions: list[NormalizedText] = Field(
        default_factory=list, max_length=MAX_CLARIFICATION_QUESTIONS
    )

    @field_validator("normalized_query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = normalize_text(value)
        if not value:
            raise ValueError("normalized_query must not be empty")
        return value

    @field_validator("ambiguities", "clarification_questions", mode="before")
    @classmethod
    def normalize_plan_lists(cls, value: Any) -> Any:
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return normalize_unique(value)
        return value

    @model_validator(mode="after")
    def validate_status_invariants(self) -> Self:
        if self.status is QueryPlanStatus.READY and (
            self.ambiguities or self.clarification_questions
        ):
            raise ValueError("ready plans cannot require clarification")
        if self.status is QueryPlanStatus.NEEDS_CLARIFICATION and (
            not self.ambiguities or not self.clarification_questions
        ):
            raise ValueError("needs_clarification requires an ambiguity and a question")
        return self
