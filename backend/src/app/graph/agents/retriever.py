from __future__ import annotations

import logging
import re
import time
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from app.application.contracts.query_plan import QueryPlan, QueryPlanStatus, normalize_unique
from app.application.contracts.retrieval import StartupSearchCriteria, TeamSizeRange
from app.application.ports.repositories import StartupDocumentRepository, StartupRepository
from app.core.config import RetrieverConfig
from app.domain.models import RecoverableError, SourceReference, StartupDocument
from app.graph.nodes import NodeName
from app.graph.state import AppState, CandidateStartup

logger = logging.getLogger(__name__)

SIZE_LABELS: dict[str, TeamSizeRange] = {
    "micro": TeamSizeRange(1, 10),
    "small": TeamSizeRange(11, 50),
    "pequena": TeamSizeRange(11, 50),
    "medium": TeamSizeRange(51, 200),
    "media": TeamSizeRange(51, 200),
    "large": TeamSizeRange(201),
    "grande": TeamSizeRange(201),
}


def build_search_criteria(plan: QueryPlan) -> StartupSearchCriteria:
    company_sizes = plan.filters.company_sizes
    ranges = tuple(item for value in company_sizes if (item := parse_team_size(value)) is not None)
    text_terms = normalize_unique([*plan.filters.keywords, *plan.filters.ai_usage_signals])
    return StartupSearchCriteria(
        sectors=tuple(value.casefold() for value in plan.filters.sectors),
        stages=tuple(value.casefold() for value in plan.filters.stages),
        locations=tuple(value.casefold() for value in plan.filters.locations),
        text_terms=tuple(value.casefold() for value in text_terms),
        team_size_ranges=ranges,
        requires_team_size_match=bool(company_sizes),
    )


def parse_team_size(value: str) -> TeamSizeRange | None:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    label = SIZE_LABELS.get(normalized.strip())
    if label is not None:
        return label
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
