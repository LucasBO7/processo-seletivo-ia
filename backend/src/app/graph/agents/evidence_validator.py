from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from uuid import UUID

from pydantic import ValidationError

from app.application.contracts.classification import (
    ClassificationStatus,
    StartupClassification,
)
from app.application.contracts.evidence_validation import (
    ClaimAssessmentOutput,
    ClaimValidation,
    ClassificationValidation,
    EvidenceStatus,
    SourceAssessment,
    SourceVerdict,
    ValidatedClassification,
    ValidatedStartupProfile,
    ValidatorOutput,
)
from app.application.contracts.extraction import (
    ExtractedFact,
    ExtractionSource,
    ProfileField,
    StructuredStartupProfile,
)
from app.application.ports.providers import ChatMessage, ChatModel
from app.core.config import EvidenceValidatorConfig
from app.domain.models import RecoverableError, SourceReference
from app.graph.model_policy import ModelRegistry
from app.graph.nodes import NodeName
from app.graph.prompts.evidence_validator import (
    PROMPT_VERSION,
    build_messages,
    build_repair_message,
)
from app.graph.state import AppState

logger = logging.getLogger(__name__)

SCALAR_FIELDS = (
    ProfileField.PRODUCT,
    ProfileField.BUSINESS_MODEL,
    ProfileField.SECTOR,
    ProfileField.TARGET_AUDIENCE,
)
LIST_FIELDS = (
    ProfileField.AI_USE_CASES,
    ProfileField.TECHNOLOGIES,
    ProfileField.INFRASTRUCTURE,
    ProfileField.EXTERNAL_DEPENDENCIES,
    ProfileField.TECHNICAL_NEEDS,
    ProfileField.CLAIMS,
)
CLASSIFICATION_KEY = "classification"


@dataclass(frozen=True, slots=True)
class ClaimItem:
    key: str
    field: ProfileField
    fact: ExtractedFact


class EvidenceValidatorAgent:
    def __init__(self, *, model: ChatModel, config: EvidenceValidatorConfig) -> None:
        self._model = model
        self._config = config

    async def __call__(self, state: AppState) -> AppState:
        started_at = time.perf_counter()
        profiles = state.get("structured_profiles", [])
        classifications_by_startup = {
            item.startup_id: item for item in state.get("classifications", [])
        }
        raw_sources = self._group_sources(state.get("selected_sources", []))
        warnings = list(state.get("warnings", []))
        errors = list(state.get("errors", []))
        claim_validations = list(state.get("claim_validations", []))
        classification_validations = list(state.get("classification_validations", []))
        validated_profiles = list(state.get("validated_profiles", []))
        validated_classifications = list(state.get("validated_classifications", []))
        model_calls = repairs = failures = source_count = 0
        processed = supported = unsupported = conflicting = insufficient = 0
        provider_failed = False

        for profile in profiles:
            items = self.enumerate_claims(profile)
            classification = classifications_by_startup.get(profile.startup_id)
            startup_sources = raw_sources.get(profile.startup_id, [])
            analyzable = [source for source in startup_sources if self._is_analyzable(source)]
            if len(analyzable) != len(startup_sources) or self._has_missing_citation(
                items, state.get("selected_sources", [])
            ):
                warnings.append("evidence_validator_source_gap")
            bounded_sources, truncated = self._bound_sources(analyzable)
            if truncated:
                warnings.append("evidence_validator_context_truncated")
            source_count += len(bounded_sources)

            requested, overflow = self._select_model_items(items, classification)
            local_assessments = {
                item.key: self._insufficient_assessment(item.key, startup_sources)
                for item in overflow
            }
            classification_local: ClaimAssessmentOutput | None = None
            if (
                classification is None
                or classification.status is ClassificationStatus.UNCERTAIN
                or not classification.evidence_references
            ):
                classification_local = self._insufficient_assessment(
                    CLASSIFICATION_KEY, startup_sources
                )

            if not bounded_sources:
                local_assessments.update(
                    {
                        item.key: self._insufficient_assessment(item.key, startup_sources)
                        for item in requested
                        if item.key != CLASSIFICATION_KEY
                    }
                )
                if classification_local is None and classification is not None:
                    classification_local = self._insufficient_assessment(
                        CLASSIFICATION_KEY, startup_sources
                    )
                output_by_key: dict[str, ClaimAssessmentOutput] = {}
            elif requested:
                system_prompt, user_prompt = build_messages(
                    items=[self._prompt_item(item) for item in requested],
                    classification=classification,
                    sources=bounded_sources,
                )
                try:
                    model_calls += 1
                    raw_candidate = await self._model.complete(
                        [
                            ChatMessage(role="system", content=system_prompt),
                            ChatMessage(role="user", content=user_prompt),
                        ]
                    )
                    output = self._parse_and_validate(raw_candidate, requested, bounded_sources)
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
                                        claim_keys=[item.key for item in requested],
                                        sources=bounded_sources,
                                    ),
                                ),
                            ]
                        )
                        output = self._parse_and_validate(raw_candidate, requested, bounded_sources)
                except Exception:
                    errors.append(self._error("evidence_validator_unavailable"))
                    failures += 1
                    provider_failed = True
                    break
                if output is None:
                    errors.append(self._error("evidence_validator_invalid_output"))
                    failures += 1
                    continue
                output_by_key = {
                    assessment.claim_key: assessment for assessment in output.assessments
                }
            else:
                output_by_key = {}

            startup_claims: list[ClaimValidation] = []
            for item in items:
                assessment = output_by_key.get(item.key) or local_assessments[item.key]
                startup_claims.append(
                    ClaimValidation(
                        startup_id=profile.startup_id,
                        field=item.field,
                        value=item.fact.value,
                        original_sources=item.fact.sources,
                        **assessment.model_dump(),
                    )
                )
            claim_validations.extend(startup_claims)
            validated_profile = self._validated_profile(profile, startup_claims)
            validated_profiles.append(validated_profile)

            classification_assessment = classification_local
            if classification_assessment is None:
                classification_assessment = output_by_key[CLASSIFICATION_KEY]
            classification_validation = ClassificationValidation(
                startup_id=profile.startup_id,
                category=classification.category if classification else None,
                **classification_assessment.model_dump(),
            )
            classification_validations.append(classification_validation)
            if (
                classification is not None
                and classification_validation.status is EvidenceStatus.SUPPORTED
            ):
                validated_classifications.append(
                    ValidatedClassification.model_validate(classification.model_dump())
                )

            for result in [*startup_claims, classification_validation]:
                if result.status is EvidenceStatus.SUPPORTED:
                    supported += 1
                elif result.status is EvidenceStatus.UNSUPPORTED:
                    unsupported += 1
                elif result.status is EvidenceStatus.CONFLICTING:
                    conflicting += 1
                else:
                    insufficient += 1
            processed += 1

        validated_claims = [
            result for result in claim_validations if result.status is EvidenceStatus.SUPPORTED
        ]
        rejected_claims = [
            result for result in claim_validations if result.status is EvidenceStatus.UNSUPPORTED
        ]
        conflicting_claims = [
            result for result in claim_validations if result.status is EvidenceStatus.CONFLICTING
        ]
        evidence_gaps = [
            result for result in claim_validations if result.status is EvidenceStatus.INSUFFICIENT
        ]
        if profiles and not validated_claims:
            warnings.append("validator_no_supported_claims")
        if not any(
            any(getattr(profile, field.value) not in (None, []) for field in ProfileField)
            for profile in validated_profiles
        ):
            warnings.append("nvidia_rag_no_usable_profiles")

        metrics = dict(state.get("metrics", {}))
        metrics.update(
            {
                "evidence_validator_duration_ms": self._duration_ms(started_at),
                "evidence_validator_startup_input_count": float(len(profiles)),
                "evidence_validator_startup_processed_count": float(processed),
                "evidence_validator_item_count": float(
                    len(claim_validations) + len(classification_validations)
                ),
                "evidence_validator_supported_count": float(supported),
                "evidence_validator_unsupported_count": float(unsupported),
                "evidence_validator_conflicting_count": float(conflicting),
                "evidence_validator_insufficient_count": float(insufficient),
                "evidence_validator_profile_count": float(len(validated_profiles)),
                "evidence_validator_classification_count": float(len(validated_classifications)),
                "evidence_validator_source_count": float(source_count),
                "evidence_validator_model_call_count": float(model_calls),
                "evidence_validator_repair_count": float(repairs),
                "evidence_validator_failure_count": float(failures),
            }
        )
        logger.log(
            logging.WARNING if provider_failed or failures else logging.INFO,
            "evidence_validator_completed",
            extra={
                "node": NodeName.EVIDENCE_VALIDATOR,
                "prompt_version": PROMPT_VERSION,
                "status": "error" if provider_failed else "completed",
                "duration_ms": metrics["evidence_validator_duration_ms"],
                "startup_count": processed,
                "item_count": supported + unsupported + conflicting + insufficient,
                "supported_count": supported,
                "failure_count": failures,
            },
        )
        return AppState(
            validated_profiles=validated_profiles,
            validated_classifications=validated_classifications,
            claim_validations=claim_validations,
            classification_validations=classification_validations,
            validated_claims=validated_claims,
            rejected_claims=rejected_claims,
            conflicting_claims=conflicting_claims,
            evidence_gaps=evidence_gaps,
            warnings=list(dict.fromkeys(warnings)),
            errors=errors,
            metrics=metrics,
        )

    @staticmethod
    def enumerate_claims(profile: StructuredStartupProfile) -> list[ClaimItem]:
        items: list[ClaimItem] = []
        for field in SCALAR_FIELDS:
            fact = getattr(profile, field.value)
            if fact is not None:
                items.append(ClaimItem(key=field.value, field=field, fact=fact))
        for field in LIST_FIELDS:
            for index, fact in enumerate(getattr(profile, field.value)):
                items.append(ClaimItem(key=f"{field.value}[{index}]", field=field, fact=fact))
        return items

    @staticmethod
    def _group_sources(sources: list[SourceReference]) -> dict[UUID, list[SourceReference]]:
        grouped: dict[UUID, list[SourceReference]] = {}
        for source in sources:
            grouped.setdefault(source.startup_id, []).append(source)
        return grouped

    @staticmethod
    def _is_analyzable(source: SourceReference) -> bool:
        return bool(source.source_url.strip() and source.excerpt and source.excerpt.strip())

    def _bound_sources(self, sources: list[SourceReference]) -> tuple[list[SourceReference], bool]:
        bounded: list[SourceReference] = []
        remaining = self._config.max_context_characters
        truncated = len(sources) > self._config.max_sources_per_startup
        for source in sources[: self._config.max_sources_per_startup]:
            excerpt = " ".join((source.excerpt or "").split())
            if remaining <= 0:
                truncated = True
                break
            if len(excerpt) > remaining:
                excerpt = excerpt[:remaining]
                truncated = True
            bounded.append(replace(source, excerpt=excerpt))
            remaining -= len(excerpt)
        return bounded, truncated

    def _select_model_items(
        self,
        items: list[ClaimItem],
        classification: StartupClassification | None,
    ) -> tuple[list[ClaimItem], list[ClaimItem]]:
        classification_is_actionable = (
            classification is not None
            and classification.status is ClassificationStatus.CLASSIFIED
            and bool(classification.evidence_references)
        )
        claim_limit = self._config.max_items_per_startup - int(classification_is_actionable)
        selected = items[: max(claim_limit, 0)]
        overflow = items[len(selected) :]
        if classification_is_actionable and classification is not None:
            placeholder = ExtractedFact(
                value=classification.justification,
                sources=classification.evidence_references,
            )
            selected.append(
                ClaimItem(
                    key=CLASSIFICATION_KEY,
                    field=ProfileField.CLAIMS,
                    fact=placeholder,
                )
            )
        return selected, overflow

    @staticmethod
    def _prompt_item(item: ClaimItem) -> dict[str, object]:
        return {
            "claim_key": item.key,
            "field": item.field.value,
            "value": item.fact.value,
            "original_sources": [source.model_dump(mode="json") for source in item.fact.sources],
        }

    def _parse_and_validate(
        self,
        candidate: str,
        requested: list[ClaimItem],
        sources: list[SourceReference],
    ) -> ValidatorOutput | None:
        try:
            output = ValidatorOutput.model_validate_json(candidate)
            expected = [item.key for item in requested]
            actual = [item.claim_key for item in output.assessments]
            if len(actual) != len(set(actual)) or set(actual) != set(expected):
                return None
            normalized = [
                self._normalize_assessment(
                    next(item for item in output.assessments if item.claim_key == key),
                    sources,
                )
                for key in expected
            ]
            if any(
                len(item.justification) > self._config.max_justification_length
                for item in normalized
            ):
                return None
            return ValidatorOutput(assessments=normalized)
        except (ValidationError, ValueError):
            return None

    @staticmethod
    def _normalize_assessment(
        assessment: ClaimAssessmentOutput, sources: list[SourceReference]
    ) -> ClaimAssessmentOutput:
        allowed = {
            (source.startup_id, source.source_id, source.source_url): index
            for index, source in enumerate(sources)
        }
        for source in assessment.analyzed_sources:
            if (source.startup_id, source.source_id, source.source_url) not in allowed:
                raise ValueError("unsupported validation source")
        ordered = sorted(
            assessment.analyzed_sources,
            key=lambda item: allowed[(item.startup_id, item.source_id, item.source_url)],
        )
        return assessment.model_copy(update={"analyzed_sources": ordered})

    @staticmethod
    def _insufficient_assessment(key: str, sources: list[SourceReference]) -> ClaimAssessmentOutput:
        return ClaimAssessmentOutput(
            claim_key=key,
            status=EvidenceStatus.INSUFFICIENT,
            justification="The available documentary evidence is insufficient.",
            analyzed_sources=[
                SourceAssessment(
                    startup_id=source.startup_id,
                    source_id=source.source_id,
                    source_url=source.source_url,
                    verdict=SourceVerdict.NOT_FOUND,
                )
                for source in sources
            ],
        )

    @staticmethod
    def _has_missing_citation(
        items: list[ClaimItem], selected_sources: list[SourceReference]
    ) -> bool:
        available = {
            (source.startup_id, source.source_id, source.source_url) for source in selected_sources
        }
        return any(
            (source.startup_id, source.source_id, source.source_url) not in available
            for item in items
            for source in item.fact.sources
        )

    @staticmethod
    def _validated_profile(
        profile: StructuredStartupProfile, validations: list[ClaimValidation]
    ) -> ValidatedStartupProfile:
        supported = {
            validation.claim_key: validation
            for validation in validations
            if validation.status is EvidenceStatus.SUPPORTED
        }

        def validated_fact(key: str, original: ExtractedFact) -> ExtractedFact | None:
            validation = supported.get(key)
            if validation is None:
                return None
            sources = [
                ExtractionSource(
                    startup_id=source.startup_id,
                    source_id=source.source_id,
                    source_url=source.source_url,
                )
                for source in validation.analyzed_sources
                if source.verdict is SourceVerdict.SUPPORTS
            ]
            return ExtractedFact(value=original.value, sources=sources)

        values: dict[str, object] = {}
        for field in SCALAR_FIELDS:
            original = getattr(profile, field.value)
            values[field.value] = (
                validated_fact(field.value, original) if original is not None else None
            )
        for field in LIST_FIELDS:
            values[field.value] = [
                result
                for index, original in enumerate(getattr(profile, field.value))
                if (result := validated_fact(f"{field.value}[{index}]", original)) is not None
            ]
        values["unknown_fields"] = [
            field
            for field in ProfileField
            if values[field.value] is None or values[field.value] == []
        ]
        return ValidatedStartupProfile(startup_id=profile.startup_id, name=profile.name, **values)

    @staticmethod
    def _error(code: str) -> RecoverableError:
        return RecoverableError(
            code=code,
            message="The evidence validator could not produce a usable result.",
            node=NodeName.EVIDENCE_VALIDATOR,
        )

    @staticmethod
    def _duration_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1_000, 3)


def create_evidence_validator_agent(
    *, registry: ModelRegistry, config: EvidenceValidatorConfig
) -> EvidenceValidatorAgent:
    return EvidenceValidatorAgent(
        model=registry.resolve(NodeName.EVIDENCE_VALIDATOR), config=config
    )
