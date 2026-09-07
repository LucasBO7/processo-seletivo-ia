from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


class Sector(StrEnum):
    FINANCIAL_SERVICES = "financial_services"
    DATA_AND_AI = "data_and_ai"
    CONVERSATIONAL_AI = "conversational_ai"
    COMMUNICATIONS = "communications"
    INDUSTRY_4_0 = "industry_4_0"
    HR_TECH = "hr_tech"
    ACCESSIBILITY = "accessibility"
    VERTICAL_SAAS = "vertical_saas"
    EVENTS_AND_TICKETING = "events_and_ticketing"
    MANAGED_IT_SERVICES = "managed_it_services"
    PRINTING_SERVICES = "printing_services"


class StartupStage(StrEnum):
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"
    GROWTH = "growth"
    LATE_STAGE = "late_stage"
    PUBLIC = "public"
    ACQUIRED = "acquired"
    BUSINESS_UNIT = "business_unit"


class CompanySize(StrEnum):
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


SECTOR_DESCRIPTIONS: dict[Sector, str] = {
    Sector.FINANCIAL_SERVICES: "finance, credit, fintech, trading and investments",
    Sector.DATA_AND_AI: "data, analytics and applied artificial intelligence",
    Sector.CONVERSATIONAL_AI: "assistants and conversational artificial intelligence",
    Sector.COMMUNICATIONS: "communications platforms and CPaaS",
    Sector.INDUSTRY_4_0: "industry 4.0, IoT and industrial automation",
    Sector.HR_TECH: "human resources and people management",
    Sector.ACCESSIBILITY: "accessibility technologies",
    Sector.VERTICAL_SAAS: "software specialized by business segment",
    Sector.EVENTS_AND_TICKETING: "events and ticketing",
    Sector.MANAGED_IT_SERVICES: "managed technology services",
    Sector.PRINTING_SERVICES: "printing and digital graphic services",
}

SECTOR_ALIASES: dict[Sector, tuple[str, ...]] = {
    Sector.FINANCIAL_SERVICES: (
        "financeiro",
        "financeira",
        "finanças",
        "financial",
        "finance",
        "fintech",
        "crédito",
        "trading",
        "investimentos",
        "fintech / crédito",
        "saas de gestão financeira",
    ),
    Sector.DATA_AND_AI: ("dados", "data", "analytics", "dados & ia", "data and ai"),
    Sector.CONVERSATIONAL_AI: (
        "ia conversacional",
        "conversational ai",
        "assistentes virtuais",
    ),
    Sector.COMMUNICATIONS: ("comunicação", "communications", "cpaas"),
    Sector.INDUSTRY_4_0: ("indústria 4.0", "industry 4.0", "iot", "automação industrial"),
    Sector.HR_TECH: ("hrtech", "rh", "recursos humanos", "human resources"),
    Sector.ACCESSIBILITY: ("acessibilidade", "accessibility"),
    Sector.VERTICAL_SAAS: ("saas vertical", "vertical saas"),
    Sector.EVENTS_AND_TICKETING: ("eventos", "ticketing", "ingressos"),
    Sector.MANAGED_IT_SERVICES: (
        "serviços de ti gerenciados",
        "managed it services",
        "managed services",
    ),
    Sector.PRINTING_SERVICES: ("impressão", "printing", "impressão online"),
}

SECTOR_PERSISTED_LABELS: dict[Sector, tuple[str, ...]] = {
    Sector.FINANCIAL_SERVICES: ("Fintech / Crédito", "SaaS de Gestão Financeira"),
    Sector.DATA_AND_AI: ("Dados & IA",),
    Sector.CONVERSATIONAL_AI: ("Conversational AI / CPaaS",),
    Sector.COMMUNICATIONS: ("CPaaS / Comunicação", "Conversational AI / CPaaS"),
    Sector.INDUSTRY_4_0: ("Indústria 4.0 / IoT+IA",),
    Sector.HR_TECH: ("HRtech",),
    Sector.ACCESSIBILITY: ("Acessibilidade / IA",),
    Sector.VERTICAL_SAAS: ("SaaS Vertical (condomínios/assinaturas)",),
    Sector.EVENTS_AND_TICKETING: ("SaaS de Eventos / Ticketing",),
    Sector.MANAGED_IT_SERVICES: ("Serviços de TI gerenciados",),
    Sector.PRINTING_SERVICES: ("SaaS de Impressão Online",),
}

STAGE_ALIASES: dict[StartupStage, tuple[str, ...]] = {
    StartupStage.PRE_SEED: ("pre-seed", "pré-seed", "pre seed"),
    StartupStage.SEED: ("seed",),
    StartupStage.SERIES_A: ("série a", "series a"),
    StartupStage.SERIES_B: ("série b", "series b"),
    StartupStage.SERIES_C: ("série c", "series c"),
    StartupStage.GROWTH: ("growth", "growth (soonicorn)", "soonicorn"),
    StartupStage.LATE_STAGE: ("late stage", "late stage / pré-ipo", "pré-ipo"),
    StartupStage.PUBLIC: ("empresa listada", "empresa listada (nasdaq)", "ipo", "nasdaq"),
    StartupStage.ACQUIRED: ("adquirida", "adquirida (m&a pela b3)", "aquisição", "m&a"),
    StartupStage.BUSINESS_UNIT: ("unidade de negócio de empresa estabelecida",),
}

STAGE_PERSISTED_LABELS: dict[StartupStage, tuple[str, ...]] = {
    StartupStage.PRE_SEED: ("Pre-seed", "Pré-seed"),
    StartupStage.SEED: ("Seed",),
    StartupStage.SERIES_A: ("Série A", "Series A"),
    StartupStage.SERIES_B: ("Série B", "Series B"),
    StartupStage.SERIES_C: ("Série C", "Series C"),
    StartupStage.GROWTH: ("Growth", "Growth (soonicorn)"),
    StartupStage.LATE_STAGE: ("Late stage", "Late stage / pré-IPO"),
    StartupStage.PUBLIC: ("Empresa listada", "Empresa listada (Nasdaq)"),
    StartupStage.ACQUIRED: ("Adquirida", "Adquirida (M&A pela B3)"),
    StartupStage.BUSINESS_UNIT: ("Unidade de negócio de empresa estabelecida",),
}

COMPANY_SIZE_ALIASES: dict[CompanySize, tuple[str, ...]] = {
    CompanySize.MICRO: ("micro",),
    CompanySize.SMALL: ("small", "pequena", "pequeno"),
    CompanySize.MEDIUM: ("medium", "média", "medio", "médio"),
    CompanySize.LARGE: ("large", "grande"),
}


def normalize_taxonomy_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip()


def _lookup[EnumType: StrEnum](
    enum_type: type[EnumType], aliases: dict[EnumType, tuple[str, ...]]
) -> dict[str, tuple[EnumType, ...]]:
    values: dict[str, list[EnumType]] = {}
    for member in enum_type:
        for raw_value in (member.value, *aliases[member]):
            key = normalize_taxonomy_key(raw_value)
            values.setdefault(key, [])
            if member not in values[key]:
                values[key].append(member)
    return {key: tuple(members) for key, members in values.items()}


SECTOR_LOOKUP = _lookup(
    Sector,
    {sector: (*SECTOR_ALIASES[sector], *SECTOR_PERSISTED_LABELS[sector]) for sector in Sector},
)
STAGE_LOOKUP = _lookup(
    StartupStage,
    {stage: (*STAGE_ALIASES[stage], *STAGE_PERSISTED_LABELS[stage]) for stage in StartupStage},
)
COMPANY_SIZE_LOOKUP = _lookup(CompanySize, COMPANY_SIZE_ALIASES)


def resolve_sectors(value: str) -> tuple[Sector, ...]:
    return SECTOR_LOOKUP.get(normalize_taxonomy_key(value), ())


def resolve_stages(value: str) -> tuple[StartupStage, ...]:
    return STAGE_LOOKUP.get(normalize_taxonomy_key(value), ())


def resolve_company_sizes(value: str) -> tuple[CompanySize, ...]:
    return COMPANY_SIZE_LOOKUP.get(normalize_taxonomy_key(value), ())


def persisted_sector_labels(sectors: list[Sector]) -> tuple[str, ...]:
    return _expanded_labels(sectors, SECTOR_PERSISTED_LABELS)


def persisted_stage_labels(stages: list[StartupStage]) -> tuple[str, ...]:
    return _expanded_labels(stages, STAGE_PERSISTED_LABELS)


def _expanded_labels[EnumType: StrEnum](
    values: list[EnumType], mappings: dict[EnumType, tuple[str, ...]]
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for label in mappings[value]:
            normalized = label.casefold()
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
    return tuple(result)
