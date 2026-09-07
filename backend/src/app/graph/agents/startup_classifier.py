from __future__ import annotations

import logging
import time
from dataclasses import replace
from uuid import UUID

from pydantic import ValidationError

from app.application.contracts.classification import (
    ClassificationSignal,
    ClassificationStatus,
    ClassifierOutput,
    ConfidenceLevel,
    StartupClassification,
)
from app.application.contracts.extraction import ExtractionSource, StructuredStartupProfile
from app.application.ports.providers import ChatMessage, ChatModel
from app.core.config import StartupClassifierConfig
from app.domain.models import RecoverableError, SourceReference
from app.graph.model_policy import ModelRegistry
from app.graph.nodes import NodeName
from app.graph.prompts.startup_classifier import (
    PROMPT_VERSION,
    build_messages,
    build_repair_message,
)
from app.graph.state import AppState

logger = logging.getLogger(__name__)

SCALAR_PROFILE_FIELDS = ("product", "business_model", "sector", "target_audience")
LIST_PROFILE_FIELDS = (
    "ai_use_cases",
    "technologies",
    "infrastructure",
    "external_dependencies",
    "technical_needs",
    "claims",
)


class StartupClassifierAgent:
    def __init__(self, *, model: ChatModel, config: StartupClassifierConfig) -> None:
        self._model = model
        self._config = config

    async def __call__(self, state: AppState) -> AppState:
        started_at = time.perf_counter()
        profiles = state.get("structured_profiles", [])
        sources_by_startup = self._group_sources(state.get("selected_sources", []))
        classifications = list(state.get("classifications", []))
        warnings = list(state.get("warnings", []))
        errors = list(state.get("errors", []))
        processed = produced = uncertain = source_count = 0
        model_calls = repairs = failures = 0
        provider_failed = False

        for profile in profiles:
            processed += 1
            profile_sources = sources_by_startup.get(profile.startup_id, [])
            bounded_sources, truncated = self._bound_sources(profile_sources)
            if truncated:
                warnings.append("classifier_context_truncated")

            if not self._has_facts(profile) or not bounded_sources:
                classifications.append(self._uncertain(profile.startup_id, profile.name))
                produced += 1
                uncertain += 1
                continue

            source_count += len(bounded_sources)
            system_prompt, user_prompt = build_messages(profile=profile, sources=bounded_sources)
            try:
                model_calls += 1
                raw_candidate = await self._model.complete(
                    [
                        ChatMessage(role="system", content=system_prompt),
                        ChatMessage(role="user", content=user_prompt),
                    ]
                )
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
                                    raw_candidate, sources=bounded_sources
                                ),
                            ),
                        ]
                    )
                    output = self._parse_and_validate(raw_candidate, bounded_sources)
            except Exception:
                errors.append(self._error("classifier_unavailable"))
                failures += 1
                provider_failed = True
                break

            if output is None:
                errors.append(self._error("classifier_invalid_output"))
                failures += 1
                continue
            classification = self._compose_classification(
                profile.startup_id, profile.name, output, bounded_sources
            )
            classifications.append(classification)
            produced += 1
            if classification.status is ClassificationStatus.UNCERTAIN:
                uncertain += 1

        if uncertain:
            warnings.append("classifier_uncertain")
        metrics = dict(state.get("metrics", {}))
        metrics.update(
            {
                "classifier_duration_ms": self._duration_ms(started_at),
                "classifier_profile_input_count": float(len(profiles)),
                "classifier_profile_processed_count": float(processed),
                "classifier_classification_count": float(produced),
                "classifier_uncertain_count": float(uncertain),
                "classifier_source_count": float(source_count),
                "classifier_model_call_count": float(model_calls),
                "classifier_repair_count": float(repairs),
                "classifier_failure_count": float(failures),
            }
        )
        logger.log(
            logging.WARNING if provider_failed or failures else logging.INFO,
            "startup_classifier_completed",
            extra={
                "node": NodeName.STARTUP_CLASSIFIER,
                "prompt_version": PROMPT_VERSION,
                "status": "error" if provider_failed else "completed",
                "duration_ms": metrics["classifier_duration_ms"],
                "profile_count": len(profiles),
                "classification_count": produced,
                "uncertain_count": uncertain,
                "source_count": source_count,
                "failure_count": failures,
            },
        )
        return AppState(
            classifications=classifications,
            warnings=list(dict.fromkeys(warnings)),
            errors=errors,
            metrics=metrics,
        )

    @staticmethod
    def _group_sources(sources: list[SourceReference]) -> dict[UUID, list[SourceReference]]:
        grouped: dict[UUID, list[SourceReference]] = {}
        for source in sources:
            if source.source_url.strip() and source.excerpt and source.excerpt.strip():
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

    @staticmethod
    def _has_facts(profile: StructuredStartupProfile) -> bool:
        return any(getattr(profile, field) is not None for field in SCALAR_PROFILE_FIELDS) or any(
            getattr(profile, field) for field in LIST_PROFILE_FIELDS
        )

    def _parse_and_validate(
        self, candidate: str, sources: list[SourceReference]
    ) -> ClassifierOutput | None:
        try:
            output = ClassifierOutput.model_validate_json(candidate)
            output = self._normalize_references(output, sources)
            if self._exceeds_limits(output):
                return None
            return output
        except (ValidationError, ValueError):
            return None

    @staticmethod
    def _normalize_references(
        output: ClassifierOutput, sources: list[SourceReference]
    ) -> ClassifierOutput:
        allowed = {
            (source.startup_id, source.source_id, source.source_url): index
            for index, source in enumerate(sources)
        }
        normalized_signals: list[ClassificationSignal] = []
        for signal in output.signals:
            for source in signal.sources:
                if (source.startup_id, source.source_id, source.source_url) not in allowed:
                    raise ValueError("unsupported classification source")
            ordered = sorted(
                signal.sources,
                key=lambda item: allowed[(item.startup_id, item.source_id, item.source_url)],
            )
            normalized_signals.append(signal.model_copy(update={"sources": ordered}))
        return output.model_copy(update={"signals": normalized_signals})

    def _exceeds_limits(self, output: ClassifierOutput) -> bool:
        return (
            len(output.justification) > self._config.max_justification_length
            or len(output.signals) > self._config.max_signals
            or any(
                len(signal.description) > self._config.max_signal_description_length
                for signal in output.signals
            )
        )

    @staticmethod
    def _compose_classification(
        startup_id: UUID,
        name: str,
        output: ClassifierOutput,
        sources: list[SourceReference],
    ) -> StartupClassification:
        cited = {
            (source.startup_id, source.source_id, source.source_url)
            for signal in output.signals
            for source in signal.sources
        }
        evidence_references = [
            ExtractionSource(
                startup_id=source.startup_id,
                source_id=source.source_id,
                source_url=source.source_url,
            )
            for source in sources
            if (source.startup_id, source.source_id, source.source_url) in cited
        ]
        return StartupClassification(
            startup_id=startup_id,
            name=name,
            evidence_references=evidence_references,
            **output.model_dump(),
        )

    @staticmethod
    def _uncertain(startup_id: UUID, name: str) -> StartupClassification:
        return StartupClassification(
            startup_id=startup_id,
            name=name,
            status=ClassificationStatus.UNCERTAIN,
            category=None,
            justification="The available evidence is insufficient for classification.",
            confidence=ConfidenceLevel.LOW,
            signals=[],
            evidence_references=[],
        )

    @staticmethod
    def _error(code: str) -> RecoverableError:
        return RecoverableError(
            code=code,
            message="The startup classifier could not produce a usable classification.",
            node=NodeName.STARTUP_CLASSIFIER,
        )

    @staticmethod
    def _duration_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1_000, 3)


def create_startup_classifier_agent(
    *, registry: ModelRegistry, config: StartupClassifierConfig
) -> StartupClassifierAgent:
    return StartupClassifierAgent(
        model=registry.resolve(NodeName.STARTUP_CLASSIFIER), config=config
    )
