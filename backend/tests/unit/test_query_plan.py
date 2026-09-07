from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.application.contracts.filter_taxonomy import CompanySize, Sector, StartupStage
from app.application.contracts.query_plan import (
    AnalysisMode,
    AnalysisStrategy,
    NumericTeamSizeRange,
    QueryPlan,
    QueryPlanStatus,
    StartupSearchFilters,
    normalize_unique,
)


def make_plan(**overrides: object) -> QueryPlan:
    values: dict[str, object] = {
        "status": "ready",
        "normalized_query": "startups brasileiras",
        "filters": {},
        "analysis_strategy": {
            "mode": "exploratory",
            "objectives": ["descobrir startups"],
            "rationale": "Consulta ampla e executável.",
        },
        "ambiguities": [],
        "clarification_questions": [],
    }
    values.update(overrides)
    return QueryPlan.model_validate(values)


def test_normalizes_and_deduplicates_text_without_changing_order() -> None:
    filters = StartupSearchFilters(
        sectors=[" financeiro ", "Financial", "FinTech"],
        company_sizes=[" pequena ", "20-30"],
        stages=["Série C", "series c"],
        locations=["São Paulo"],
        keywords=["computer vision"],
        ai_usage_signals=["LLM"],
    )

    assert filters.sectors == [Sector.FINANCIAL_SERVICES]
    assert filters.company_sizes == [
        CompanySize.SMALL,
        NumericTeamSizeRange(minimum=20, maximum=30),
    ]
    assert filters.stages == [StartupStage.SERIES_C]
    assert normalize_unique([" A ", "a", " B  C "]) == ["A", "B C"]


@pytest.mark.parametrize("mode", list(AnalysisMode))
def test_accepts_each_analysis_mode(mode: AnalysisMode) -> None:
    plan = make_plan(
        analysis_strategy={
            "mode": mode,
            "objectives": [" comparar soluções "],
            "rationale": "  Motivo   curto. ",
        }
    )

    assert plan.analysis_strategy.mode is mode
    assert plan.analysis_strategy.rationale == "Motivo curto."


def test_missing_filter_values_are_empty_lists() -> None:
    plan = make_plan()

    assert plan.filters.model_dump() == {
        "sectors": [],
        "company_sizes": [],
        "stages": [],
        "locations": [],
        "keywords": [],
        "ai_usage_signals": [],
    }


def test_clarification_requires_ambiguity_and_question() -> None:
    with pytest.raises(ValidationError, match="requires an ambiguity and a question"):
        make_plan(status="needs_clarification")

    plan = make_plan(
        status="needs_clarification",
        ambiguities=[" porte pode significar receita ou equipe "],
        clarification_questions=["Qual definição de porte deve ser usada?"],
    )
    assert plan.status is QueryPlanStatus.NEEDS_CLARIFICATION


def test_ready_rejects_clarification_and_extra_fields() -> None:
    with pytest.raises(ValidationError, match="cannot require clarification"):
        make_plan(ambiguities=["ambígua"])
    with pytest.raises(ValidationError, match="Extra inputs"):
        make_plan(unexpected="value")
    with pytest.raises(ValidationError):
        make_plan(filters={"sectors": ["unknown_sector"]})


def test_contract_limits_and_serialization() -> None:
    with pytest.raises(ValidationError):
        AnalysisStrategy(
            mode="targeted",
            objectives=[],
            rationale="x" * 501,
        )

    dumped = make_plan().model_dump(mode="json")
    assert dumped["status"] == "ready"
    assert dumped["analysis_strategy"]["mode"] == "exploratory"


def test_unresolved_filter_requires_three_matching_enum_suggestions() -> None:
    plan = make_plan(
        status="needs_clarification",
        ambiguities=["Setor não reconhecido."],
        clarification_questions=["Qual categoria representa o setor?"],
        unresolved_filters=[{"field": "sector", "requested_value": "agricultura espacial"}],
        filter_suggestions=[
            {
                "field": "sector",
                "requested_value": "agricultura espacial",
                "options": ["industry_4_0", "data_and_ai", "managed_it_services"],
            }
        ],
    )

    assert plan.filter_suggestions[0].options == [
        Sector.INDUSTRY_4_0,
        Sector.DATA_AND_AI,
        Sector.MANAGED_IT_SERVICES,
    ]


@pytest.mark.parametrize(
    "suggestion",
    [
        {
            "field": "sector",
            "requested_value": "desconhecido",
            "options": ["seed", "series_a", "growth"],
        },
        {
            "field": "sector",
            "requested_value": "desconhecido",
            "options": ["data_and_ai", "data_and_ai", "industry_4_0"],
        },
    ],
)
def test_rejects_invalid_filter_suggestions(suggestion: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_plan(
            status="needs_clarification",
            ambiguities=["Setor não reconhecido."],
            clarification_questions=["Qual categoria?"],
            unresolved_filters=[{"field": "sector", "requested_value": "desconhecido"}],
            filter_suggestions=[suggestion],
        )
