from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

import pytest

from app.evaluation.cli import _safe_live_api, _safe_run_id, execute
from app.evaluation.live import _from_api
from app.evaluation.loader import load_dataset, load_predictions, load_thresholds
from app.evaluation.metrics import METRIC_NAMES, evaluate
from app.evaluation.models import EvaluationDataset, PredictionSet, ThresholdSet
from app.evaluation.report import render_markdown

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_ROOT = BACKEND_ROOT / "evaluation"


def reference_inputs() -> tuple[EvaluationDataset, PredictionSet, ThresholdSet]:
    return (
        load_dataset(EVALUATION_ROOT / "cases.v1.json"),
        load_predictions(EVALUATION_ROOT / "predictions.reference.v1.json"),
        load_thresholds(EVALUATION_ROOT / "thresholds.v1.json"),
    )


def test_reference_benchmark_passes_every_threshold() -> None:
    dataset, predictions, thresholds = reference_inputs()
    report = evaluate(dataset, predictions, thresholds)

    assert report.passed
    assert len(report.metrics) == len(METRIC_NAMES)
    assert report.reranking_after_mrr > report.reranking_before_mrr
    assert report.human_rubric_status == "evaluated"
    assert all(metric.passed and not metric.failed_cases for metric in report.metrics)


def test_regression_identifies_metric_and_case() -> None:
    dataset, predictions, thresholds = reference_inputs()
    first = predictions.predictions[0].model_copy(
        update={"classification": "non-ai", "recommended_technologies": ["isaac"]}
    )
    regressed = PredictionSet(version="v1", predictions=[first, *predictions.predictions[1:]])

    report = evaluate(dataset, regressed, thresholds, run_id="regression")

    assert not report.passed
    classification = next(
        metric for metric in report.metrics if metric.name == "classification_accuracy"
    )
    forbidden = next(
        metric for metric in report.metrics if metric.name == "forbidden_recommendation_avoidance"
    )
    assert classification.failed_cases == ["hand-talk-accessibility"]
    assert forbidden.failed_cases == ["hand-talk-accessibility"]


def test_missing_rubric_is_explicit_and_does_not_fake_human_evaluation() -> None:
    dataset, predictions, thresholds = reference_inputs()
    without_rubric = PredictionSet(
        version="v1",
        predictions=[item.model_copy(update={"rubric": None}) for item in predictions.predictions],
    )

    report = evaluate(dataset, without_rubric, thresholds)

    assert report.human_rubric_status == "not_evaluated"
    assert report.passed
    rubric = next(metric for metric in report.metrics if metric.name == "subjective_rubric")
    assert rubric.value is None and rubric.passed is None


def test_report_contains_aggregates_but_not_queries_or_evidence_text() -> None:
    dataset, predictions, thresholds = reference_inputs()
    report = evaluate(dataset, predictions, thresholds)

    markdown = render_markdown(report)

    assert "Efeito do reranking" in markdown
    assert "Antes (híbrida)" in markdown
    assert dataset.cases[0].query not in markdown
    assert "tradução automática" not in markdown


def test_prediction_coverage_must_match_dataset() -> None:
    dataset, predictions, thresholds = reference_inputs()
    incomplete = PredictionSet(version="v1", predictions=predictions.predictions[:-1])

    with pytest.raises(ValueError, match="coverage mismatch"):
        evaluate(dataset, incomplete, thresholds)


def test_reranking_must_compare_the_same_candidates() -> None:
    dataset, predictions, thresholds = reference_inputs()
    first = predictions.predictions[0].model_copy(update={"nvidia_before_rerank": []})
    inconsistent = PredictionSet(version="v1", predictions=[first, *predictions.predictions[1:]])

    with pytest.raises(ValueError, match="candidate sets differ"):
        evaluate(dataset, inconsistent, thresholds)


def test_live_mode_requires_explicit_environment_before_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("RUN_LIVE_EVALUATION", raising=False)
    monkeypatch.setattr(
        "app.evaluation.cli.collect_live_predictions",
        lambda *_: pytest.fail("network adapter must not run"),
    )
    arguments = argparse.Namespace(
        cases=EVALUATION_ROOT / "cases.v1.json",
        thresholds=EVALUATION_ROOT / "thresholds.v1.json",
        predictions=EVALUATION_ROOT / "predictions.reference.v1.json",
        output_dir=tmp_path,
        run_id="blocked",
        live_api="http://127.0.0.1:8000",
    )

    with pytest.raises(SystemExit, match="RUN_LIVE_EVALUATION=1"):
        execute(arguments)


@pytest.mark.parametrize(
    ("validator", "unsafe_value"),
    [
        (_safe_live_api, "https://token@example.com"),
        (_safe_run_id, "../outside"),
    ],
)
def test_cli_rejects_credentials_and_unsafe_report_paths(
    validator: Callable[[str], str], unsafe_value: str
) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        validator(unsafe_value)


def test_offline_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    arguments = argparse.Namespace(
        cases=EVALUATION_ROOT / "cases.v1.json",
        thresholds=EVALUATION_ROOT / "thresholds.v1.json",
        predictions=EVALUATION_ROOT / "predictions.reference.v1.json",
        output_dir=tmp_path,
        run_id="test-report",
        live_api=None,
    )

    assert execute(arguments) == 0
    assert (tmp_path / "test-report.md").is_file()
    assert (tmp_path / "test-report.json").is_file()


def test_public_api_payload_is_normalized_for_scoring() -> None:
    payload = {
        "query_plan": {
            "status": "ready",
            "filters": {"sectors": ["accessibility"]},
        },
        "candidate_startups": [{"name": "Hand Talk"}],
        "validated_profiles": [{"product": {"value": "Tradução com IA"}, "ai_use_cases": []}],
        "validated_classifications": [{"category": "ai-native"}],
        "claim_validations": [{"claim_key": "product:0", "status": "supported"}],
        "nvidia_contexts": [
            {
                "chunks": [
                    {
                        "source_key": "riva",
                        "source_url": "https://developer.nvidia.com/riva",
                        "scores": {"hybrid_score": 0.4},
                    },
                    {
                        "source_key": "nvidia-nim",
                        "source_url": "https://www.nvidia.com/nim",
                        "scores": {"hybrid_score": 0.9},
                    },
                ]
            }
        ],
        "selected_sources": [{"source_url": "https://www.handtalk.me/br/"}],
        "recommendations": [{"technology": "riva"}],
    }

    prediction = _from_api("hand-talk-accessibility", payload)

    assert prediction.ranked_startups == ["Hand Talk"]
    assert prediction.profile_facts["product"] == ["Tradução com IA"]
    assert [item.source_key for item in prediction.nvidia_before_rerank] == [
        "nvidia-nim",
        "riva",
    ]
    assert [item.source_key for item in prediction.nvidia_after_rerank] == [
        "riva",
        "nvidia-nim",
    ]
