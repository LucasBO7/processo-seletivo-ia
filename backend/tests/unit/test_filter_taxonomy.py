from __future__ import annotations

import pytest

from app.application.contracts.filter_taxonomy import (
    CompanySize,
    Sector,
    StartupStage,
    normalize_taxonomy_key,
    persisted_sector_labels,
    persisted_stage_labels,
    resolve_company_sizes,
    resolve_sectors,
    resolve_stages,
)


@pytest.mark.parametrize(
    "alias",
    ["financeiro", "finanças", "FINANCIAL", "FinTech", "crédito", "trading", "investimentos"],
)
def test_financial_aliases_resolve_to_canonical_sector(alias: str) -> None:
    assert resolve_sectors(alias) == (Sector.FINANCIAL_SERVICES,)


def test_taxonomy_normalization_ignores_accents_case_and_spaces() -> None:
    assert normalize_taxonomy_key("  GESTÃO   Financeira ") == "gestao financeira"
    assert resolve_company_sizes("  MÉDIA ") == (CompanySize.MEDIUM,)
    assert resolve_stages("SÉRIE C") == (StartupStage.SERIES_C,)


def test_canonical_sector_expands_to_existing_financial_labels() -> None:
    assert persisted_sector_labels([Sector.FINANCIAL_SERVICES]) == (
        "fintech / crédito",
        "saas de gestão financeira",
    )


def test_compound_persisted_label_can_belong_to_multiple_sectors() -> None:
    assert "conversational ai / cpaas" in persisted_sector_labels(
        [Sector.CONVERSATIONAL_AI, Sector.COMMUNICATIONS]
    )
    assert resolve_sectors("Conversational AI / CPaaS") == (
        Sector.CONVERSATIONAL_AI,
        Sector.COMMUNICATIONS,
    )


def test_stage_expansion_preserves_known_persisted_variants() -> None:
    assert persisted_stage_labels([StartupStage.GROWTH]) == (
        "growth",
        "growth (soonicorn)",
    )
