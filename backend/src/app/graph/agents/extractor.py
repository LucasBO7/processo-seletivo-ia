from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from dataclasses import replace
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.application.contracts.extraction import (
    ExtractedFact,
    ExtractorOutput,
    ProfileField,
    StructuredStartupProfile,
)
from app.application.ports.providers import ChatMessage, ChatModel
from app.core.config import ExtractorConfig
from app.domain.models import RecoverableError, SourceReference
from app.graph.model_policy import ModelRegistry
from app.graph.nodes import NodeName
from app.graph.prompts.extractor import (
    PROMPT_VERSION,
    build_messages,
    build_repair_message,
)
from app.graph.state import AppState

logger = logging.getLogger(__name__)

SCALAR_FIELDS = ("product", "business_model", "sector", "target_audience")
LIST_FIELDS = (
    "ai_use_cases",
    "technologies",
    "infrastructure",
    "external_dependencies",
    "technical_needs",
    "claims",
)


class ExtractorAgent:
    def __init__(self, *, model: ChatModel, config: ExtractorConfig) -> None:
        self._model = model
        self._config = config

    async def __call__(self, state: AppState) -> AppState:
        started_at = time.perf_counter()
        candidates = state.get("candidate_startups", [])
        selected_sources = state.get("selected_sources", [])
        warnings = list(state.get("warnings", []))
        errors = list(state.get("errors", []))
        profiles = list(state.get("structured_profiles", []))
        produced_profiles = 0
        processed = model_calls = repairs = failures = used_source_count = 0

        candidate_ids = {candidate["startup_id"] for candidate in candidates}
        sources_by_startup = self._group_sources(selected_sources, candidate_ids)
        sourced_candidates = [
            candidate for candidate in candidates if sources_by_startup.get(candidate["startup_id"])
        ]
        if candidates and len(sourced_candidates) != len(candidates):
            warnings.append("extractor_sources_missing")

        provider_failed = False
        for candidate in sourced_candidates:
            bounded_sources, truncated = self._bound_sources(
                sources_by_startup[candidate["startup_id"]]
            )
            if truncated and "extractor_context_truncated" not in warnings:
                warnings.append("extractor_context_truncated")
            if not bounded_sources:
                continue
            used_source_count += len(bounded_sources)
            processed += 1
            system_prompt, user_prompt = build_messages(
                startup_name=candidate["name"], sources=bounded_sources
            )
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ]
            try:
                model_calls += 1
                raw_candidate = await self._model.complete(messages)
                output = self._parse_and_validate(raw_candidate, bounded_sources)
                attempt = 0
                while output is None and attempt < self._config.max_repair_attempts:
                    attempt += 1
                    repairs += 1
                    model_calls += 1
                    raw_candidate = await self._model.complete(
                        [
                            ChatMessage(role="system", content=system_prompt),
                            ChatMessage(
                                role="user",
                                content=build_repair_message(
                                    raw_candidate,
                                    sources=bounded_sources,
                                ),
                            ),
                        ]
                    )
                    output = self._parse_and_validate(raw_candidate, bounded_sources)
            except Exception:
                errors.append(self._error("extractor_unavailable"))
                failures += 1
                provider_failed = True
                break

            if output is None:
                errors.append(self._error("extractor_invalid_output"))
                failures += 1
                continue
            profiles.append(
                StructuredStartupProfile(
                    startup_id=candidate["startup_id"],
                    name=candidate["name"],
                    **output.model_dump(),
                )
            )
            produced_profiles += 1

        metrics = dict(state.get("metrics", {}))
        metrics.update(
            {
                "extractor_duration_ms": self._duration_ms(started_at),
                "extractor_startup_input_count": float(len(candidates)),
                "extractor_startup_processed_count": float(processed),
                "extractor_profile_count": float(produced_profiles),
                "extractor_source_count": float(used_source_count),
                "extractor_model_call_count": float(model_calls),
                "extractor_repair_count": float(repairs),
                "extractor_failure_count": float(failures),
            }
        )
        logger.log(
            logging.WARNING if provider_failed or failures else logging.INFO,
            "extractor_completed",
            extra={
                "node": NodeName.EXTRACTOR,
                "prompt_version": PROMPT_VERSION,
                "status": "error" if provider_failed else "completed",
                "duration_ms": metrics["extractor_duration_ms"],
                "startup_count": processed,
                "source_count": used_source_count,
                "profile_count": produced_profiles,
                "failure_count": failures,
            },
        )
        return AppState(
            structured_profiles=profiles,
            warnings=list(dict.fromkeys(warnings)),
            errors=errors,
            metrics=metrics,
        )

    @staticmethod
    def _group_sources(
        sources: list[SourceReference], candidate_ids: set[UUID]
    ) -> dict[UUID, list[SourceReference]]:
        grouped: dict[UUID, list[SourceReference]] = {}
        for source in sources:
            if (
                source.startup_id in candidate_ids
                and source.source_url.strip()
                and source.excerpt
                and source.excerpt.strip()
            ):
                grouped.setdefault(source.startup_id, []).append(source)
        return grouped

    def _bound_sources(self, sources: list[SourceReference]) -> tuple[list[SourceReference], bool]:
        bounded: list[SourceReference] = []
        remaining = self._config.max_context_characters
        truncated = len(sources) > self._config.max_sources_per_startup
        for source in sources[: self._config.max_sources_per_startup]:
            excerpt = " ".join((source.excerpt or "").split())
            if not excerpt or remaining <= 0:
                truncated = True
                break
            if len(excerpt) > remaining:
                excerpt = excerpt[:remaining]
                truncated = True
            bounded.append(replace(source, excerpt=excerpt))
            remaining -= len(excerpt)
        return bounded, truncated

    def _parse_and_validate(
        self, candidate: str, sources: list[SourceReference]
    ) -> ExtractorOutput | None:
        try:
            payload = json.loads(candidate)
            if isinstance(payload, list) and len(payload) == 1:
                payload = payload[0]
            if not isinstance(payload, dict):
                return None
            payload = self._normalize_output_shape(payload)
            output = ExtractorOutput.model_validate(payload)
            output = self._normalize_citations(output, sources)
            if self._exceeds_limits(output):
                return None
            return output
        except (json.JSONDecodeError, ValidationError, ValueError):
            return None

    @staticmethod
    def _normalize_output_shape(payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        for field in SCALAR_FIELDS:
            if normalized.get(field) == []:
                normalized[field] = None
        for field in LIST_FIELDS:
            if normalized.get(field) is None:
                normalized[field] = []
        normalized["unknown_fields"] = [
            field.value
            for field in ProfileField
            if normalized.get(field.value) is None or normalized.get(field.value) == []
        ]
        return normalized

    def _normalize_citations(
        self, output: ExtractorOutput, sources: list[SourceReference]
    ) -> ExtractorOutput:
        allowed = {
            (source.startup_id, source.source_id, source.source_url): index
            for index, source in enumerate(sources)
        }

        def normalize(fact: ExtractedFact) -> ExtractedFact:
            for source in fact.sources:
                if (source.startup_id, source.source_id, source.source_url) not in allowed:
                    raise ValueError("unsupported extraction source")
            ordered = sorted(
                fact.sources,
                key=lambda item: allowed[(item.startup_id, item.source_id, item.source_url)],
            )
            return fact.model_copy(update={"sources": ordered})

        updates: dict[str, Any] = {}
        for field in SCALAR_FIELDS:
            fact = getattr(output, field)
            updates[field] = normalize(fact) if fact is not None else None
        for field in LIST_FIELDS:
            updates[field] = [normalize(fact) for fact in getattr(output, field)]
        return output.model_copy(update=updates)

    def _exceeds_limits(self, output: ExtractorOutput) -> bool:
        facts: Iterable[ExtractedFact] = (
            fact
            for field in (*SCALAR_FIELDS, *LIST_FIELDS)
            for fact in self._facts(getattr(output, field))
        )
        return any(len(fact.value) > self._config.max_fact_length for fact in facts) or any(
            len(getattr(output, field)) > self._config.max_items_per_list for field in LIST_FIELDS
        )

    @staticmethod
    def _facts(value: ExtractedFact | list[ExtractedFact] | None) -> list[ExtractedFact]:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    @staticmethod
    def _error(code: str) -> RecoverableError:
        return RecoverableError(
            code=code,
            message="The extractor could not produce a usable startup profile.",
            node=NodeName.EXTRACTOR,
        )

    @staticmethod
    def _duration_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1_000, 3)


def create_extractor_agent(*, registry: ModelRegistry, config: ExtractorConfig) -> ExtractorAgent:
    return ExtractorAgent(model=registry.resolve(NodeName.EXTRACTOR), config=config)
