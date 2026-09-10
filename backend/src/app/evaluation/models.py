from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExpectedPlan(StrictModel):
    status: Literal["ready", "needs_clarification", "invalid"]
    filters: dict[str, list[str]]


class ExpectedProfile(StrictModel):
    required_facts: dict[str, list[str]]
    forbidden_facts: list[str] = Field(default_factory=list)


class EvaluationExpected(StrictModel):
    plan: ExpectedPlan
    relevant_startups: list[str] = Field(min_length=1)
    profile: ExpectedProfile
    classification: Literal["ai-native", "ai-enabled", "non-ai", "uncertain"]
    evidence_statuses: dict[str, Literal["supported", "unsupported", "conflicting", "insufficient"]]
    relevant_nvidia_sources: list[str] = Field(min_length=1)
    citation_urls: list[str] = Field(min_length=1)
    acceptable_technologies: list[str] = Field(min_length=1)
    forbidden_recommendations: list[str] = Field(default_factory=list)


class EvaluationCase(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    origin: Literal["real_snapshot", "synthetic"]
    reviewed_at: str
    reference_urls: list[str]
    query: str = Field(min_length=1, max_length=2_000)
    expected: EvaluationExpected


class EvaluationDataset(StrictModel):
    version: str = Field(pattern=r"^v[0-9]+$")
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_case_ids(self) -> EvaluationDataset:
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluation case ids must be unique")
        return self


class PredictedPlan(StrictModel):
    status: str
    filters: dict[str, list[str]]


class RankedNvidiaItem(StrictModel):
    source_key: str
    source_url: str


class RubricScores(StrictModel):
    relevance: int = Field(ge=1, le=4)
    grounding: int = Field(ge=1, le=4)
    specificity: int = Field(ge=1, le=4)
    actionability: int = Field(ge=1, le=4)

    def normalized_score(self) -> float:
        values = [self.relevance, self.grounding, self.specificity, self.actionability]
        if min(values) < 2:
            return 0.0
        return sum(values) / (len(values) * 4)


class EvaluationPrediction(StrictModel):
    case_id: str
    plan: PredictedPlan
    ranked_startups: list[str]
    profile_facts: dict[str, list[str]]
    classification: str
    evidence_statuses: dict[str, str]
    nvidia_before_rerank: list[RankedNvidiaItem]
    nvidia_after_rerank: list[RankedNvidiaItem]
    citation_urls: list[str]
    recommended_technologies: list[str]
    rubric: RubricScores | None = None


class PredictionSet(StrictModel):
    version: str = Field(pattern=r"^(?:v[0-9]+|live-v[0-9]+)$")
    predictions: list[EvaluationPrediction] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_case_ids(self) -> PredictionSet:
        ids = [prediction.case_id for prediction in self.predictions]
        if len(ids) != len(set(ids)):
            raise ValueError("prediction case ids must be unique")
        return self


class ThresholdSet(StrictModel):
    version: str = Field(pattern=r"^v[0-9]+$")
    metrics: dict[str, float]

    @field_validator("metrics")
    @classmethod
    def values_are_rates(cls, values: dict[str, float]) -> dict[str, float]:
        if not values or any(value < 0 or value > 1 for value in values.values()):
            raise ValueError("metric thresholds must be in [0, 1]")
        return values


class MetricResult(StrictModel):
    name: str
    value: float | None
    threshold: float
    passed: bool | None
    failed_cases: list[str]


class EvaluationReport(StrictModel):
    dataset_version: str
    prediction_version: str
    run_id: str
    mode: Literal["offline", "live"]
    passed: bool
    metrics: list[MetricResult]
    reranking_before_mrr: float
    reranking_after_mrr: float
    reranking_delta_mrr: float
    evaluated_cases: int
    human_rubric_status: Literal["evaluated", "not_evaluated"]
