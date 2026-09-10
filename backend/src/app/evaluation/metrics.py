from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable
from statistics import fmean
from typing import Literal
from urllib.parse import urlsplit

from app.evaluation.models import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationPrediction,
    EvaluationReport,
    MetricResult,
    PredictionSet,
    ThresholdSet,
)

METRIC_NAMES = (
    "query_structure",
    "startup_recall_at_5",
    "startup_precision_at_5",
    "startup_mrr",
    "extraction_fact_recall",
    "forbidden_fact_avoidance",
    "classification_accuracy",
    "factual_support_accuracy",
    "nvidia_recall_at_5",
    "nvidia_precision_at_5",
    "reranking_after_mrr",
    "reranking_delta_mrr",
    "citation_url_validity",
    "citation_recall",
    "recommendation_acceptance",
    "forbidden_recommendation_avoidance",
    "subjective_rubric",
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", ascii_text).strip().casefold()


def _set_f1(expected: Iterable[str], actual: Iterable[str]) -> float:
    expected_set = {_normalize(value) for value in expected}
    actual_set = {_normalize(value) for value in actual}
    if not expected_set:
        return 1.0 if not actual_set else 0.0
    overlap = len(expected_set & actual_set)
    precision = overlap / len(actual_set) if actual_set else 0.0
    recall = overlap / len(expected_set)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _recall_at(expected: Iterable[str], actual: Iterable[str], k: int) -> float:
    expected_set = {_normalize(value) for value in expected}
    if not expected_set:
        return 1.0
    actual_set = {_normalize(value) for value in list(actual)[:k]}
    return len(expected_set & actual_set) / len(expected_set)


def _precision_at(expected: Iterable[str], actual: Iterable[str], k: int) -> float:
    expected_set = {_normalize(value) for value in expected}
    actual_values = list(actual)[:k]
    if not actual_values:
        return 0.0
    return sum(_normalize(value) in expected_set for value in actual_values) / len(actual_values)


def _reciprocal_rank(expected: Iterable[str], actual: Iterable[str]) -> float:
    expected_set = {_normalize(value) for value in expected}
    for rank, value in enumerate(actual, start=1):
        if _normalize(value) in expected_set:
            return 1 / rank
    return 0.0


def _query_structure(case: EvaluationCase, prediction: EvaluationPrediction) -> float:
    status = float(case.expected.plan.status == prediction.plan.status)
    fields = set(case.expected.plan.filters) | set(prediction.plan.filters)
    filter_score = (
        fmean(
            _set_f1(
                case.expected.plan.filters.get(field, []), prediction.plan.filters.get(field, [])
            )
            for field in fields
        )
        if fields
        else 1.0
    )
    return 0.4 * status + 0.6 * filter_score


def _extraction_recall(case: EvaluationCase, prediction: EvaluationPrediction) -> float:
    scores: list[float] = []
    for field, expected_facts in case.expected.profile.required_facts.items():
        actual = [_normalize(value) for value in prediction.profile_facts.get(field, [])]
        for fact in expected_facts:
            scores.append(float(any(_normalize(fact) in value for value in actual)))
    return fmean(scores) if scores else 1.0


def _forbidden_fact_avoidance(case: EvaluationCase, prediction: EvaluationPrediction) -> float:
    output = " ".join(
        _normalize(value) for values in prediction.profile_facts.values() for value in values
    )
    return float(
        not any(_normalize(value) in output for value in case.expected.profile.forbidden_facts)
    )


def _factual_support(case: EvaluationCase, prediction: EvaluationPrediction) -> float:
    expected = case.expected.evidence_statuses
    if not expected:
        return 1.0
    return sum(
        prediction.evidence_statuses.get(key) == value for key, value in expected.items()
    ) / len(expected)


def _valid_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and not parsed.username
        and not parsed.password
    )


def _citation_validity(_: EvaluationCase, prediction: EvaluationPrediction) -> float:
    return (
        sum(_valid_url(url) for url in prediction.citation_urls) / len(prediction.citation_urls)
        if prediction.citation_urls
        else 0.0
    )


def _recommendation_acceptance(case: EvaluationCase, prediction: EvaluationPrediction) -> float:
    if not prediction.recommended_technologies:
        return 0.0
    acceptable = {_normalize(value) for value in case.expected.acceptable_technologies}
    return sum(
        _normalize(value) in acceptable for value in prediction.recommended_technologies
    ) / len(prediction.recommended_technologies)


def _forbidden_recommendation_avoidance(
    case: EvaluationCase, prediction: EvaluationPrediction
) -> float:
    forbidden = {_normalize(value) for value in case.expected.forbidden_recommendations}
    actual = {_normalize(value) for value in prediction.recommended_technologies}
    return float(not (forbidden & actual))


MetricFunction = Callable[[EvaluationCase, EvaluationPrediction], float]


def _metric_functions() -> dict[str, MetricFunction]:
    return {
        "query_structure": _query_structure,
        "startup_recall_at_5": lambda case, prediction: _recall_at(
            case.expected.relevant_startups, prediction.ranked_startups, 5
        ),
        "startup_precision_at_5": lambda case, prediction: _precision_at(
            case.expected.relevant_startups, prediction.ranked_startups, 5
        ),
        "startup_mrr": lambda case, prediction: _reciprocal_rank(
            case.expected.relevant_startups, prediction.ranked_startups
        ),
        "extraction_fact_recall": _extraction_recall,
        "forbidden_fact_avoidance": _forbidden_fact_avoidance,
        "classification_accuracy": lambda case, prediction: float(
            case.expected.classification == prediction.classification
        ),
        "factual_support_accuracy": _factual_support,
        "nvidia_recall_at_5": lambda case, prediction: _recall_at(
            case.expected.relevant_nvidia_sources,
            [item.source_key for item in prediction.nvidia_after_rerank],
            5,
        ),
        "nvidia_precision_at_5": lambda case, prediction: _precision_at(
            case.expected.relevant_nvidia_sources,
            [item.source_key for item in prediction.nvidia_after_rerank],
            5,
        ),
        "reranking_after_mrr": lambda case, prediction: _reciprocal_rank(
            case.expected.relevant_nvidia_sources,
            [item.source_key for item in prediction.nvidia_after_rerank],
        ),
        "citation_url_validity": _citation_validity,
        "citation_recall": lambda case, prediction: _recall_at(
            case.expected.citation_urls, prediction.citation_urls, len(prediction.citation_urls)
        ),
        "recommendation_acceptance": _recommendation_acceptance,
        "forbidden_recommendation_avoidance": _forbidden_recommendation_avoidance,
        "subjective_rubric": lambda _case, prediction: (
            prediction.rubric.normalized_score() if prediction.rubric else 0.0
        ),
    }


def evaluate(
    dataset: EvaluationDataset,
    predictions: PredictionSet,
    thresholds: ThresholdSet,
    *,
    run_id: str = "offline-reference",
    mode: Literal["offline", "live"] = "offline",
) -> EvaluationReport:
    by_case = {prediction.case_id: prediction for prediction in predictions.predictions}
    missing = [case.id for case in dataset.cases if case.id not in by_case]
    unknown = sorted(set(by_case) - {case.id for case in dataset.cases})
    if missing or unknown:
        raise ValueError(f"prediction coverage mismatch: missing={missing}, unknown={unknown}")
    if set(thresholds.metrics) != set(METRIC_NAMES):
        raise ValueError("threshold metrics do not match the supported metric set")

    for prediction in predictions.predictions:
        before = sorted(item.source_key for item in prediction.nvidia_before_rerank)
        after = sorted(item.source_key for item in prediction.nvidia_after_rerank)
        if before != after:
            raise ValueError(f"reranking candidate sets differ for case {prediction.case_id}")

    before_scores = [
        _reciprocal_rank(
            case.expected.relevant_nvidia_sources,
            [item.source_key for item in by_case[case.id].nvidia_before_rerank],
        )
        for case in dataset.cases
    ]
    after_scores = [
        _reciprocal_rank(
            case.expected.relevant_nvidia_sources,
            [item.source_key for item in by_case[case.id].nvidia_after_rerank],
        )
        for case in dataset.cases
    ]
    before_mrr = fmean(before_scores)
    after_mrr = fmean(after_scores)
    delta = after_mrr - before_mrr

    functions = _metric_functions()
    rubric_available = all(by_case[case.id].rubric is not None for case in dataset.cases)
    metric_results: list[MetricResult] = []
    for name in METRIC_NAMES:
        threshold = thresholds.metrics[name]
        if name == "subjective_rubric" and not rubric_available:
            metric_results.append(
                MetricResult(
                    name=name,
                    value=None,
                    threshold=threshold,
                    passed=None,
                    failed_cases=[],
                )
            )
            continue
        if name == "reranking_delta_mrr":
            values = {
                case.id: after_score - before_score
                for case, before_score, after_score in zip(
                    dataset.cases, before_scores, after_scores, strict=True
                )
            }
        else:
            function = functions[name]
            values = {case.id: function(case, by_case[case.id]) for case in dataset.cases}
        value = fmean(values.values())
        metric_results.append(
            MetricResult(
                name=name,
                value=value,
                threshold=threshold,
                passed=value >= threshold,
                failed_cases=sorted(
                    case_id for case_id, score in values.items() if score < threshold
                ),
            )
        )

    return EvaluationReport(
        dataset_version=dataset.version,
        prediction_version=predictions.version,
        run_id=run_id,
        mode=mode,
        passed=all(result.passed is not False for result in metric_results),
        metrics=metric_results,
        reranking_before_mrr=before_mrr,
        reranking_after_mrr=after_mrr,
        reranking_delta_mrr=delta,
        evaluated_cases=len(dataset.cases),
        human_rubric_status="evaluated" if rubric_available else "not_evaluated",
    )
