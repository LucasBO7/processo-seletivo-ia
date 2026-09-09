from __future__ import annotations

from uuid import uuid4

import pytest

from app.api.routes.search import AnalysisOutcome, analysis_outcome, public_metrics
from app.application.contracts.query_plan import QueryPlan
from app.graph.state import AppState


def make_plan(status: str) -> QueryPlan:
    clarification = status == "needs_clarification"
    return QueryPlan.model_validate(
        {
            "status": status,
            "normalized_query": "startups",
            "filters": {},
            "analysis_strategy": {
                "mode": "exploratory",
                "objectives": ["analisar startups"],
                "rationale": "Consulta analisável.",
            },
            "ambiguities": ["setor"] if clarification else [],
            "clarification_questions": ["Qual setor?"] if clarification else [],
        }
    )


@pytest.mark.parametrize(
    ("state", "status_code", "expected"),
    [
        (
            AppState(candidate_startups=[{"startup_id": uuid4(), "name": "A", "score": 1.0}]),
            200,
            AnalysisOutcome.SUCCESS,
        ),
        (
            AppState(query_plan=make_plan("needs_clarification")),
            200,
            AnalysisOutcome.NEEDS_CLARIFICATION,
        ),
        (AppState(query_plan=make_plan("invalid")), 422, AnalysisOutcome.INVALID_QUERY),
        (AppState(query_plan=make_plan("ready")), 200, AnalysisOutcome.NO_RESULTS),
        (AppState(), 503, AnalysisOutcome.TEMPORARILY_UNAVAILABLE),
        (AppState(), 502, AnalysisOutcome.INTERNAL_FAILURE),
        (AppState(), 500, AnalysisOutcome.INTERNAL_FAILURE),
    ],
)
def test_analysis_outcome_is_deterministic(
    state: AppState, status_code: int, expected: AnalysisOutcome
) -> None:
    assert analysis_outcome(state, status_code) is expected


def test_public_metrics_keeps_only_finite_agent_metrics() -> None:
    assert public_metrics(
        {
            "extractor_duration_ms": 2.5,
            "nvidia_rag_contexts": 1.0,
            "sql_query_duration_ms": 4.0,
            "briefing_nan": float("nan"),
        }
    ) == {
        "extractor_duration_ms": 2.5,
        "nvidia_rag_contexts": 1.0,
    }
