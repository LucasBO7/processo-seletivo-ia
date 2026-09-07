from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.contracts.filter_taxonomy import (
    CompanySize,
    Sector,
    StartupStage,
    resolve_company_sizes,
    resolve_sectors,
    resolve_stages,
)

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


def _deduplicate(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = json.dumps(value, sort_keys=True) if isinstance(value, dict) else str(value)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _normalize_enum_list(value: Any, resolver: Any) -> Any:
    if not isinstance(value, list):
        return value
    result: list[Any] = []
    for item in value:
        if isinstance(item, str):
            resolved = resolver(item)
            result.extend(resolved or [item])
        else:
            result.append(item)
    return _deduplicate(result)


def _numeric_team_size(value: str) -> dict[str, int | None] | None:
    normalized = normalize_text(value).casefold()
    numbers = [int(item) for item in re.findall(r"\d+", normalized)]
    if len(numbers) >= 2:
        return {"minimum": min(numbers[0], numbers[1]), "maximum": max(numbers[0], numbers[1])}
    if len(numbers) == 1:
        number = numbers[0]
        if "+" in normalized or "mais" in normalized:
            return {"minimum": number, "maximum": None}
        if "até" in normalized or "ate" in normalized or "<=" in normalized:
            return {"minimum": 0, "maximum": number}
        return {"minimum": number, "maximum": number}
    return None


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


class NumericTeamSizeRange(StrictContract):
    minimum: int = Field(ge=0)
    maximum: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.maximum is not None and self.maximum < self.minimum:
            raise ValueError("maximum must be greater than or equal to minimum")
        return self


class StartupSearchFilters(StrictContract):
    sectors: list[Sector] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    company_sizes: list[CompanySize | NumericTeamSizeRange] = Field(
        default_factory=list, max_length=MAX_LIST_ITEMS
    )
    stages: list[StartupStage] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    locations: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    keywords: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    ai_usage_signals: list[NormalizedText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)

    @field_validator("sectors", mode="before")
    @classmethod
    def normalize_sectors(cls, value: Any) -> Any:
        return _normalize_enum_list(value, resolve_sectors)

    @field_validator("stages", mode="before")
    @classmethod
    def normalize_stages(cls, value: Any) -> Any:
        return _normalize_enum_list(value, resolve_stages)

    @field_validator("company_sizes", mode="before")
    @classmethod
    def normalize_company_sizes(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        result: list[Any] = []
        for item in value:
            if isinstance(item, str):
                resolved = resolve_company_sizes(item)
                numeric_range = _numeric_team_size(item)
                result.extend(resolved or ([numeric_range] if numeric_range else [item]))
            else:
                result.append(item)
        return _deduplicate(result)

    @field_validator("locations", "keywords", "ai_usage_signals", mode="before")
    @classmethod
    def normalize_text_lists(cls, value: Any) -> Any:
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return normalize_unique(value)
        return value


class FilterField(StrEnum):
    SECTOR = "sector"
    STAGE = "stage"
    COMPANY_SIZE = "company_size"


class UnresolvedFilter(StrictContract):
    field: FilterField
    requested_value: NormalizedText

    @field_validator("requested_value")
    @classmethod
    def normalize_requested_value(cls, value: str) -> str:
        return normalize_text(value)


SuggestionOption = Sector | StartupStage | CompanySize


class FilterSuggestion(StrictContract):
    field: FilterField
    requested_value: NormalizedText
    options: list[SuggestionOption] = Field(min_length=3, max_length=3)

    @field_validator("requested_value")
    @classmethod
    def normalize_requested_value(cls, value: str) -> str:
        return normalize_text(value)

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        expected_type: type[StrEnum] = {
            FilterField.SECTOR: Sector,
            FilterField.STAGE: StartupStage,
            FilterField.COMPANY_SIZE: CompanySize,
        }[self.field]
        if any(type(option) is not expected_type for option in self.options):
            raise ValueError("suggestion options must belong to the selected field")
        if len(set(self.options)) != len(self.options):
            raise ValueError("suggestion options must be unique")
        return self


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
    unresolved_filters: list[UnresolvedFilter] = Field(
        default_factory=list, max_length=MAX_LIST_ITEMS
    )
    filter_suggestions: list[FilterSuggestion] = Field(
        default_factory=list, max_length=MAX_LIST_ITEMS
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
            self.ambiguities
            or self.clarification_questions
            or self.unresolved_filters
            or self.filter_suggestions
        ):
            raise ValueError("ready plans cannot require clarification")
        if self.status is QueryPlanStatus.NEEDS_CLARIFICATION and (
            not self.ambiguities or not self.clarification_questions
        ):
            raise ValueError("needs_clarification requires an ambiguity and a question")
        unresolved = {
            (item.field, item.requested_value.casefold()) for item in self.unresolved_filters
        }
        suggested = {
            (item.field, item.requested_value.casefold()) for item in self.filter_suggestions
        }
        if unresolved != suggested:
            raise ValueError("each unresolved filter requires exactly one matching suggestion")
        if unresolved and self.status is not QueryPlanStatus.NEEDS_CLARIFICATION:
            raise ValueError("unresolved filters require needs_clarification status")
        return self
