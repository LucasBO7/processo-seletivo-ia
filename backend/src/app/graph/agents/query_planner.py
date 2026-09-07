from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from app.application.contracts.query_plan import QueryPlan, QueryPlanStatus, normalize_text
from app.application.ports.providers import ChatMessage, ChatModel
from app.core.config import QueryPlannerConfig
from app.domain.models import RecoverableError
from app.graph.model_policy import ModelRegistry
from app.graph.nodes import NodeName
from app.graph.prompts.query_planner import (
    PROMPT_VERSION,
    build_messages,
    build_repair_message,
)
from app.graph.state import AppState

logger = logging.getLogger(__name__)


class QueryPlannerAgent:
    def __init__(self, *, model: ChatModel, config: QueryPlannerConfig) -> None:
        self._model = model
        self._config = config

    async def __call__(self, state: AppState) -> AppState:
        started_at = time.perf_counter()
        query = state.get("query", "").strip()
        input_error = self._validate_query(query)
        if input_error:
            return self._error_update(input_error, started_at, state=state)

        system_prompt, user_prompt = build_messages(query)
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]
        try:
            candidate = await self._model.complete(messages)
            parsed = self._parse(candidate, query)
            attempts = 0
            while parsed is None and attempts < self._config.max_repair_attempts:
                attempts += 1
                candidate = await self._model.complete(
                    [
                        ChatMessage(role="system", content=system_prompt),
                        ChatMessage(role="user", content=build_repair_message(candidate)),
                    ]
                )
                parsed = self._parse(candidate, query)
        except Exception:
            return self._error_update("query_planner_unavailable", started_at, state=state)

        if parsed is None:
            return self._error_update("query_plan_invalid_output", started_at, state=state)
        plan, filters_normalized = parsed
        limit_error = self._validate_configured_limits(plan)
        if limit_error:
            return self._error_update("query_plan_invalid_output", started_at, state=state)

        duration_ms = self._duration_ms(started_at)
        warnings = list(state.get("warnings", []))
        if filters_normalized:
            warnings.append("query_filter_normalized")
        warnings += (
            ["query_plan_needs_clarification"]
            if plan.status is QueryPlanStatus.NEEDS_CLARIFICATION
            else []
        )
        errors = list(state.get("errors", []))
        errors += (
            [self._recoverable_error("query_invalid")]
            if plan.status is QueryPlanStatus.INVALID
            else []
        )
        metrics = dict(state.get("metrics", {}))
        metrics["query_planner_duration_ms"] = duration_ms
        logger.info(
            "query_planner_completed",
            extra={
                "node": NodeName.QUERY_PLANNER,
                "prompt_version": PROMPT_VERSION,
                "status": plan.status,
                "duration_ms": duration_ms,
                "item_count": self._item_count(plan),
            },
        )
        return AppState(
            query_plan=plan,
            warnings=warnings,
            errors=errors,
            metrics=metrics,
        )

    def _validate_query(self, query: str) -> str | None:
        if not query or not any(character.isalnum() for character in query):
            return "query_empty"
        if len(query) > self._config.max_query_length:
            return "query_too_long"
        return None

    def _parse(self, candidate: str, query: str) -> tuple[QueryPlan, bool] | None:
        try:
            payload = json.loads(candidate)
            if not isinstance(payload, dict):
                return None
            plan = QueryPlan.model_validate(payload)
            filters_normalized = self._filters_were_normalized(payload, plan)
            return (
                plan.model_copy(update={"normalized_query": normalize_text(query)}),
                filters_normalized,
            )
        except (json.JSONDecodeError, ValidationError):
            return None

    def _validate_configured_limits(self, plan: QueryPlan) -> bool:
        lists: Sequence[Sequence[Any]] = (
            plan.filters.sectors,
            plan.filters.company_sizes,
            plan.filters.stages,
            plan.filters.locations,
            plan.filters.keywords,
            plan.filters.ai_usage_signals,
            plan.analysis_strategy.objectives,
            plan.ambiguities,
            plan.unresolved_filters,
            plan.filter_suggestions,
        )
        return (
            any(len(items) > self._config.max_items_per_list for items in lists)
            or len(plan.clarification_questions) > self._config.max_clarification_questions
            or len(plan.analysis_strategy.rationale) > self._config.max_rationale_length
        )

    @staticmethod
    def _filters_were_normalized(payload: dict[str, Any], plan: QueryPlan) -> bool:
        raw_filters = payload.get("filters")
        if not isinstance(raw_filters, dict):
            return False
        canonical = plan.filters.model_dump(mode="json")
        return any(
            raw_filters.get(field, []) != canonical[field]
            for field in ("sectors", "company_sizes", "stages")
        )

    def _error_update(
        self, code: str, started_at: float, *, state: AppState | None = None
    ) -> AppState:
        duration_ms = self._duration_ms(started_at)
        logger.warning(
            "query_planner_failed",
            extra={
                "node": NodeName.QUERY_PLANNER,
                "prompt_version": PROMPT_VERSION,
                "status": "error",
                "duration_ms": duration_ms,
                "error_code": code,
            },
        )
        previous = state or AppState()
        errors = [*previous.get("errors", []), self._recoverable_error(code)]
        metrics = dict(previous.get("metrics", {}))
        metrics["query_planner_duration_ms"] = duration_ms
        return AppState(errors=errors, warnings=list(previous.get("warnings", [])), metrics=metrics)

    @staticmethod
    def _recoverable_error(code: str) -> RecoverableError:
        return RecoverableError(
            code=code,
            message="The query planner could not produce a usable plan.",
            node=NodeName.QUERY_PLANNER,
        )

    @staticmethod
    def _duration_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1_000, 3)

    @staticmethod
    def _item_count(plan: QueryPlan) -> int:
        return sum(
            len(items)
            for items in (
                plan.filters.sectors,
                plan.filters.company_sizes,
                plan.filters.stages,
                plan.filters.locations,
                plan.filters.keywords,
                plan.filters.ai_usage_signals,
                plan.unresolved_filters,
                plan.filter_suggestions,
            )
        )


def create_query_planner_agent(
    *, registry: ModelRegistry, config: QueryPlannerConfig
) -> QueryPlannerAgent:
    return QueryPlannerAgent(model=registry.resolve(NodeName.QUERY_PLANNER), config=config)
