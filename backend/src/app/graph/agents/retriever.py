from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from app.application.contracts.filter_taxonomy import (
    CompanySize,
    normalize_taxonomy_key,
    persisted_sector_labels,
    persisted_stage_labels,
    resolve_company_sizes,
)
from app.application.contracts.query_plan import (
    AnalysisMode,
    NumericTeamSizeRange,
    QueryPlan,
    QueryPlanStatus,
    normalize_unique,
)
from app.application.contracts.retrieval import RankedStartup, StartupSearchCriteria, TeamSizeRange
from app.application.ports.repositories import StartupDocumentRepository, StartupRepository
from app.core.config import RetrieverConfig
from app.domain.models import RecoverableError, SourceReference, StartupDocument
from app.graph.nodes import NodeName
from app.graph.state import AppState, CandidateStartup

logger = logging.getLogger(__name__)

SIZE_RANGES: dict[CompanySize, TeamSizeRange] = {
    CompanySize.MICRO: TeamSizeRange(1, 10),
    CompanySize.SMALL: TeamSizeRange(11, 50),
    CompanySize.MEDIUM: TeamSizeRange(51, 200),
    CompanySize.LARGE: TeamSizeRange(201),
}
BRAZIL_COUNTRY_SCOPE = {"brasil", "brazil"}


def normalize_locations(values: list[str]) -> tuple[str, ...]:
    if any(normalize_taxonomy_key(value) in BRAZIL_COUNTRY_SCOPE for value in values):
        return ()
    return tuple(value.casefold() for value in values)


def build_search_criteria(plan: QueryPlan) -> StartupSearchCriteria:
    company_sizes = plan.filters.company_sizes
    ranges = tuple(item for value in company_sizes if (item := parse_team_size(value)) is not None)
    text_terms = normalize_unique([*plan.filters.keywords, *plan.filters.ai_usage_signals])
    return StartupSearchCriteria(
        sectors=persisted_sector_labels(plan.filters.sectors),
        stages=persisted_stage_labels(plan.filters.stages),
        locations=normalize_locations(plan.filters.locations),
        text_terms=tuple(value.casefold() for value in text_terms),
        team_size_ranges=ranges,
        requires_team_size_match=bool(company_sizes),
    )


def parse_team_size(value: CompanySize | NumericTeamSizeRange | str) -> TeamSizeRange | None:
    if isinstance(value, NumericTeamSizeRange):
        return TeamSizeRange(value.minimum, value.maximum)
    if isinstance(value, CompanySize):
        return SIZE_RANGES[value]
    resolved = resolve_company_sizes(value)
    if resolved:
        return SIZE_RANGES[resolved[0]]
    normalized = normalize_taxonomy_key(value)
    numbers = [int(item) for item in re.findall(r"\d+", normalized)]
    if len(numbers) >= 2:
        return TeamSizeRange(min(numbers[0], numbers[1]), max(numbers[0], numbers[1]))
    if len(numbers) == 1:
        number = numbers[0]
        if "+" in normalized or "mais" in normalized:
            return TeamSizeRange(number)
        if "ate" in normalized or "<=" in normalized:
            return TeamSizeRange(0, number)
        return TeamSizeRange(number, number)
    return None


def retain_explicitly_named_startups(
    plan: QueryPlan, ranked: list[RankedStartup]
) -> list[RankedStartup]:
    """Narrow targeted searches when a keyword is exactly a returned startup name."""
    if plan.analysis_strategy.mode is not AnalysisMode.TARGETED:
        return ranked
    keywords = {normalize_taxonomy_key(value) for value in plan.filters.keywords}
    named = [item for item in ranked if normalize_taxonomy_key(item.startup.name) in keywords]
    return named or ranked


class RetrieverAgent:
    def __init__(
        self,
        *,
        startups: StartupRepository,
        documents: StartupDocumentRepository,
        config: RetrieverConfig,
    ) -> None:
        self._startups = startups
        self._documents = documents
        self._config = config

    async def __call__(self, state: AppState) -> AppState:
        started_at = time.perf_counter()
        plan = state.get("query_plan")
        if plan is None:
            return self._error_update("retriever_plan_missing", state, started_at)
        if plan.status is not QueryPlanStatus.READY:
            return self._error_update("retriever_plan_not_ready", state, started_at)

        try:
            ranked = await self._startups.search(
                build_search_criteria(plan), limit=self._config.max_results
            )
            ranked = retain_explicitly_named_startups(plan, ranked)
            documents = (
                await self._documents.list_for_startups([item.startup.id for item in ranked])
                if ranked
                else []
            )
        except Exception:
            return self._error_update("retriever_unavailable", state, started_at)

        candidate_startups = [
            CandidateStartup(
                startup_id=item.startup.id,
                name=item.startup.name,
                score=item.score,
            )
            for item in ranked
        ]
        sources = self._ordered_sources(
            ranked_ids=[item.startup.id for item in ranked], documents=documents
        )
        warnings = list(state.get("warnings", []))
        if not ranked:
            warnings.append("retriever_no_results")
        elif not any(
            source.source_url.strip() and source.excerpt and source.excerpt.strip()
            for source in sources
        ):
            warnings.append("retriever_no_sources")
        duration_ms = self._duration_ms(started_at)
        metrics = dict(state.get("metrics", {}))
        metrics.update(
            {
                "retriever_duration_ms": duration_ms,
                "retriever_startup_count": float(len(ranked)),
                "retriever_source_count": float(len(sources)),
            }
        )
        logger.info(
            "retriever_completed",
            extra={
                "node": NodeName.RETRIEVER,
                "duration_ms": duration_ms,
                "startup_count": len(ranked),
                "source_count": len(sources),
            },
        )
        return AppState(
            candidate_startups=candidate_startups,
            selected_sources=sources,
            warnings=warnings,
            errors=list(state.get("errors", [])),
            metrics=metrics,
        )

    def _ordered_sources(
        self, *, ranked_ids: list[UUID], documents: list[StartupDocument]
    ) -> list[SourceReference]:
        grouped: dict[UUID, list[StartupDocument]] = defaultdict(list)
        for document in documents:
            grouped[document.startup_id].append(document)
        for startup_documents in grouped.values():
            startup_documents.sort(key=lambda item: item.id)
            startup_documents.sort(key=lambda item: item.title.casefold())
            startup_documents.sort(
                key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )
        return [
            SourceReference(
                startup_id=document.startup_id,
                source_id=document.id,
                source_url=document.source_url,
                title=document.title,
                excerpt=self._excerpt(document.content_text),
            )
            for startup_id in ranked_ids
            for document in grouped[startup_id]
        ]

    def _excerpt(self, content: str) -> str:
        normalized = re.sub(r"\s+", " ", content).strip()
        return normalized[: self._config.excerpt_length]

    def _error_update(self, code: str, state: AppState, started_at: float) -> AppState:
        duration_ms = self._duration_ms(started_at)
        errors = [
            *state.get("errors", []),
            RecoverableError(
                code=code,
                message="The retriever could not complete the search.",
                node=NodeName.RETRIEVER,
            ),
        ]
        metrics = dict(state.get("metrics", {}))
        metrics["retriever_duration_ms"] = duration_ms
        logger.warning(
            "retriever_failed",
            extra={
                "node": NodeName.RETRIEVER,
                "duration_ms": duration_ms,
                "error_code": code,
            },
        )
        return AppState(
            errors=errors,
            warnings=list(state.get("warnings", [])),
            metrics=metrics,
        )

    @staticmethod
    def _duration_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1_000, 3)
