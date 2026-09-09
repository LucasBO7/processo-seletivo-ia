from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from app.application.contracts.evidence_validation import (
    EvidenceStatus,
    ValidatedClassification,
    ValidatedStartupProfile,
)
from app.application.contracts.extraction import ExtractedFact, ProfileField
from app.application.contracts.nvidia_rag import (
    NvidiaContextStatus,
    NvidiaRetrievedChunk,
    NvidiaStartupContext,
)
from app.application.contracts.recommendation import (
    BusinessRelevance,
    ComplexityBasis,
    EvidenceStrength,
    ImplementationComplexity,
    InfrastructureChange,
    IntegrationScope,
    NeedCriticality,
    NvidiaRecommendationEvidence,
    PriorityBasis,
    RecommendationCandidate,
    RecommendationCandidateBatch,
    RecommendationNeed,
    RecommendationNeedKind,
    RecommendationPriority,
    SpecializedSkills,
    StartupRecommendation,
    StartupRecommendationEvidence,
)
from app.application.ports.providers import ChatMessage, ChatModel
from app.core.config import RecommendationConfig
from app.domain.models import RecoverableError
from app.graph.model_policy import ModelRegistry
from app.graph.nodes import NodeName
from app.graph.prompts.json_format import compact_json
from app.graph.prompts.recommendation import PROMPT_VERSION, build_messages, build_repair_message
from app.graph.state import AppState

logger = logging.getLogger(__name__)

BUSINESS_FIELDS = {
    ProfileField.PRODUCT,
    ProfileField.BUSINESS_MODEL,
    ProfileField.TARGET_AUDIENCE,
    ProfileField.AI_USE_CASES,
    ProfileField.CLAIMS,
}
PROFILE_FIELD_ORDER = tuple(ProfileField)
BLOCKER_TERMS = (
    "block",
    "mandatory",
    "required",
    "failure",
    "imped",
    "obrigat",
    "falha",
    "requisito",
)
CORE_TERMS = ("core", "central", "depends", "depende", "produto", "product", "primary")
API_TERMS = ("api", "microservice", "microserviço", "managed service", "serviço gerenciado")
PLATFORM_TERMS = ("platform", "plataforma", "migration", "migração", "migrate", "migrar")
MAJOR_TERMS = ("major", "substantial", "large-scale", "rebuild", "grande", "ampla")
ADVANCED_TERMS = ("advanced", "expert", "especialista", "avançad")
ACTION_TERMS = (
    "discovery",
    "descoberta",
    "validat",
    "aderência",
    "fit",
    "demo",
    "workshop",
    "proof of concept",
    "prova de conceito",
    "poc",
    "referral",
    "encaminhamento",
)
PROHIBITED_PROMISES = (
    "guarantee",
    "garantia",
    "guaranteed",
    "roi certo",
    "retorno garantido",
    "contrato garantido",
    "will deliver",
    "será entregue",
)
DEPLOYED_CLAIMS = ("already deployed", "já implant", "already uses", "já utiliza")
UNSUPPORTED_ESTIMATES = (
    "week",
    "semana",
    "month",
    "mês",
    "price",
    "preço",
    "cost",
    "custo",
    "engineer",
    "pessoas",
    "gpu count",
    "quantidade de gpu",
)
MATURITY_TERMS = ("maturity", "maturidade", "ai-native", "ai-enabled", "non-ai")


@dataclass(frozen=True, slots=True)
class PreparedStartup:
    profile: ValidatedStartupProfile
    classification: ValidatedClassification | None
    context: NvidiaStartupContext
    needs: list[RecommendationNeed]
    evidence: list[StartupRecommendationEvidence]
    chunks: list[NvidiaRetrievedChunk]
    business_evidence_ids: frozenset[UUID]
    truncated: bool


class RecommendationSemanticError(ValueError):
    def __init__(self, violations: list[str]) -> None:
        super().__init__("invalid recommendation batch")
        self.violations = list(dict.fromkeys(violations))


def calculate_priority(
    criticality: NeedCriticality,
    relevance: BusinessRelevance,
    strength: EvidenceStrength,
) -> tuple[int, RecommendationPriority]:
    score = {
        NeedCriticality.OPTIMIZATION: 0,
        NeedCriticality.IMPORTANT: 1,
        NeedCriticality.BLOCKER: 2,
    }[criticality]
    score += 1 if relevance is BusinessRelevance.CORE else 0
    score += 1 if strength is EvidenceStrength.CORROBORATED else 0
    if score == 0:
        return score, RecommendationPriority.LOW
    if score <= 2:
        return score, RecommendationPriority.MEDIUM
    return score, RecommendationPriority.HIGH


def calculate_complexity(
    scope: IntegrationScope,
    infrastructure: InfrastructureChange,
    skills: SpecializedSkills,
) -> tuple[int, ImplementationComplexity]:
    score = {
        IntegrationScope.CONFIGURATION_OR_API: 0,
        IntegrationScope.SINGLE_COMPONENT: 1,
        IntegrationScope.PLATFORM_OR_MIGRATION: 2,
    }[scope]
    score += {
        InfrastructureChange.NONE: 0,
        InfrastructureChange.MODERATE: 1,
        InfrastructureChange.MAJOR: 2,
    }[infrastructure]
    score += {
        SpecializedSkills.STANDARD: 0,
        SpecializedSkills.SPECIALIZED: 1,
        SpecializedSkills.ADVANCED: 2,
    }[skills]
    if score <= 1:
        return score, ImplementationComplexity.LOW
    if score <= 3:
        return score, ImplementationComplexity.MEDIUM
    return score, ImplementationComplexity.HIGH


class RecommendationAgent:
    def __init__(self, *, model: ChatModel, config: RecommendationConfig) -> None:
        self._model = model
        self._config = config

    async def __call__(self, state: AppState) -> AppState:
        started_at = time.perf_counter()
        warnings = list(state.get("warnings", []))
        errors = list(state.get("errors", []))
        recommendations = list(state.get("recommendations", []))
        metrics = dict(state.get("metrics", {}))
        counters = self._empty_counters()
        profiles = state.get("validated_profiles", [])
        counters["input_startup_count"] = float(len(profiles))
        contexts = {item.startup_id: item for item in state.get("nvidia_contexts", [])}
        classifications = {
            item.startup_id: item for item in state.get("validated_classifications", [])
        }

        prepared_items: list[PreparedStartup] = []
        context_eligible_count = 0
        for profile in profiles:
            context = contexts.get(profile.startup_id)
            if not self.is_eligible_context(profile, context):
                warnings.append("recommendation_nvidia_context_insufficient")
                counters["skipped_context_count"] += 1
                continue
            assert context is not None
            context_eligible_count += 1
            prepared, local_warnings, reason = self._prepare(
                profile,
                classifications.get(profile.startup_id),
                context,
                state,
            )
            warnings.extend(local_warnings)
            if prepared is None:
                counters[reason] += 1
                continue
            prepared_items.append(prepared)

        counters["eligible_startup_count"] = float(len(prepared_items))
        if not context_eligible_count:
            warnings.append("recommendation_no_eligible_startups")

        for prepared in prepared_items:
            counters["processed_startup_count"] += 1
            if prepared.classification is None:
                warnings.append("recommendation_classification_unavailable")
            if prepared.truncated:
                warnings.append("recommendation_context_truncated")
            counters["need_count"] += float(len(prepared.needs))
            counters["nvidia_chunk_count"] += float(len(prepared.chunks))
            context_payload = self._prompt_context(prepared)
            system_prompt, user_prompt = build_messages(context_payload)
            raw_candidate = ""
            try:
                counters["model_call_count"] += 1
                raw_candidate = await self._model.complete(
                    [
                        ChatMessage(role="system", content=system_prompt),
                        ChatMessage(role="user", content=user_prompt),
                    ]
                )
                batch, violations = self._parse_and_validate(raw_candidate, prepared)
                attempt = 0
                while batch is None and attempt < self._config.max_repair_attempts:
                    attempt += 1
                    counters["repair_count"] += 1
                    counters["model_call_count"] += 1
                    raw_candidate = await self._model.complete(
                        [
                            ChatMessage(role="system", content=system_prompt),
                            ChatMessage(
                                role="user",
                                content=build_repair_message(
                                    raw_candidate,
                                    violations=violations,
                                    need_keys=[item.key for item in prepared.needs],
                                    startup_evidence_ids=[
                                        str(item.source_id) for item in prepared.evidence
                                    ],
                                    nvidia_chunk_ids=[
                                        str(item.chunk_id) for item in prepared.chunks
                                    ],
                                ),
                            ),
                        ]
                    )
                    batch, violations = self._parse_and_validate(raw_candidate, prepared)
            except Exception:
                errors.append(self._error("recommendation_unavailable"))
                counters["failure_count"] += 1
                continue
            if batch is None:
                errors.append(self._error("recommendation_invalid_output"))
                counters["invalid_batch_count"] += 1
                counters["failure_count"] += 1
                continue
            if not batch:
                warnings.append("recommendation_no_compatible_match")
                continue
            recommendations.extend(batch)
            counters["accepted_count"] += float(len(batch))

        recommendations.sort(key=self._sort_key)
        return self._patch(started_at, recommendations, warnings, errors, metrics, counters)

    @staticmethod
    def is_eligible_context(
        profile: ValidatedStartupProfile, context: NvidiaStartupContext | None
    ) -> bool:
        return bool(
            context is not None
            and context.startup_id == profile.startup_id
            and context.sufficiency.status is NvidiaContextStatus.SUFFICIENT
            and any(chunk.startup_id == profile.startup_id for chunk in context.chunks)
        )

    def _prepare(
        self,
        profile: ValidatedStartupProfile,
        classification: ValidatedClassification | None,
        context: NvidiaStartupContext,
        state: AppState,
    ) -> tuple[PreparedStartup | None, list[str], str]:
        warnings: list[str] = []
        evidence = self._profile_evidence(profile)
        evidence_by_id: dict[UUID, list[StartupRecommendationEvidence]] = {}
        for item in evidence:
            evidence_by_id.setdefault(item.source_id, []).append(item)
        approved_ids = {
            source.source_id
            for claim in state.get("validated_claims", [])
            if claim.startup_id == profile.startup_id and claim.status is EvidenceStatus.SUPPORTED
            for source in claim.analyzed_sources
            if source.verdict.value == "supports"
        } | set(evidence_by_id)

        needs: list[RecommendationNeed] = []
        for fact in profile.technical_needs:
            ids = [
                source.source_id
                for source in fact.sources
                if source.startup_id == profile.startup_id
            ]
            if ids:
                needs.append(
                    RecommendationNeed(
                        key=f"need:{len(needs) + 1}",
                        kind=RecommendationNeedKind.VALIDATED_TECHNICAL_NEED,
                        description=fact.value,
                        startup_evidence_ids=ids,
                    )
                )
        for gap in state.get("technical_gaps", []):
            ids = list(dict.fromkeys(item for item in gap.evidence_ids if item in approved_ids))
            if not ids:
                warnings.append("recommendation_gap_untraceable")
                continue
            needs.append(
                RecommendationNeed(
                    key=f"need:{len(needs) + 1}",
                    kind=RecommendationNeedKind.VALIDATED_TECHNICAL_GAP,
                    description=gap.description,
                    startup_evidence_ids=ids,
                )
            )
        if not needs:
            warnings.append("recommendation_no_identified_need")
            return None, warnings, "skipped_no_need_count"

        business_ids = {item.source_id for item in evidence if item.field in BUSINESS_FIELDS}
        if not business_ids:
            warnings.append("recommendation_business_context_insufficient")
            return None, warnings, "skipped_business_context_count"

        truncated = False
        if len(needs) > self._config.max_needs_per_startup:
            needs = needs[: self._config.max_needs_per_startup]
            truncated = True
        unique_evidence: list[StartupRecommendationEvidence] = []
        seen_evidence: set[tuple[UUID, ProfileField, str]] = set()
        for item in evidence:
            key = (item.source_id, item.field, item.value)
            if key not in seen_evidence:
                seen_evidence.add(key)
                unique_evidence.append(item)
        need_evidence_ids = {source_id for need in needs for source_id in need.startup_evidence_ids}
        unique_evidence.sort(
            key=lambda item: (
                0
                if item.source_id in need_evidence_ids and item.source_id in business_ids
                else 1
                if item.source_id in business_ids
                else 2
                if item.source_id in need_evidence_ids
                else 3
            )
        )
        if len(unique_evidence) > self._config.max_startup_evidence:
            unique_evidence = unique_evidence[: self._config.max_startup_evidence]
            truncated = True
        retained_ids = {item.source_id for item in unique_evidence}
        retained_needs = [item for item in needs if retained_ids & set(item.startup_evidence_ids)]
        if len(retained_needs) != len(needs):
            needs = retained_needs
            truncated = True
        retained_business_ids = business_ids & retained_ids
        if not needs:
            warnings.append("recommendation_no_identified_need")
            return None, warnings, "skipped_no_need_count"
        if not retained_business_ids:
            warnings.append("recommendation_business_context_insufficient")
            return None, warnings, "skipped_business_context_count"
        chunks = [item for item in context.chunks if item.startup_id == profile.startup_id]
        if len(chunks) > self._config.max_nvidia_chunks:
            chunks = chunks[: self._config.max_nvidia_chunks]
            truncated = True
        if not chunks:
            warnings.append("recommendation_nvidia_context_insufficient")
            return None, warnings, "skipped_context_count"

        prepared = PreparedStartup(
            profile=profile,
            classification=classification,
            context=context,
            needs=needs,
            evidence=unique_evidence,
            chunks=chunks,
            business_evidence_ids=frozenset(retained_business_ids),
            truncated=truncated,
        )
        return self._bound_characters(prepared), warnings, "skipped_no_need_count"

    @staticmethod
    def _profile_evidence(
        profile: ValidatedStartupProfile,
    ) -> list[StartupRecommendationEvidence]:
        result: list[StartupRecommendationEvidence] = []
        for field in PROFILE_FIELD_ORDER:
            value = getattr(profile, field.value)
            facts: list[ExtractedFact] = (
                value if isinstance(value, list) else ([value] if value else [])
            )
            for fact in facts:
                for source in fact.sources:
                    if source.startup_id == profile.startup_id:
                        result.append(
                            StartupRecommendationEvidence(
                                startup_id=profile.startup_id,
                                source_id=source.source_id,
                                source_url=source.source_url,
                                field=field,
                                value=fact.value,
                            )
                        )
        return result

    def _bound_characters(self, prepared: PreparedStartup) -> PreparedStartup:
        payload = self._prompt_context(prepared, apply_char_limit=False)
        if len(compact_json(payload)) <= self._config.max_context_characters:
            return prepared
        chunks: list[NvidiaRetrievedChunk] = []
        remaining = self._config.max_context_characters // 2
        for chunk in prepared.chunks:
            if remaining <= 0:
                break
            content = chunk.content[:remaining].rstrip()
            if content:
                chunks.append(chunk.model_copy(update={"content": content}))
                remaining -= len(content)
        return PreparedStartup(
            profile=prepared.profile,
            classification=prepared.classification,
            context=prepared.context,
            needs=prepared.needs,
            evidence=prepared.evidence,
            chunks=chunks or prepared.chunks[:1],
            business_evidence_ids=prepared.business_evidence_ids,
            truncated=True,
        )

    def _prompt_context(
        self, prepared: PreparedStartup, *, apply_char_limit: bool = True
    ) -> dict[str, object]:
        needs_payload = [item.model_dump(mode="json") for item in prepared.needs]
        evidence_payload: list[dict[str, object]] = [
            {
                "source_id": str(item.source_id),
                "field": item.field.value,
                "value": item.value,
            }
            for item in prepared.evidence
        ]
        chunks_payload: list[dict[str, object]] = [
            {
                "chunk_id": str(item.chunk_id),
                "technology": item.technology.value,
                "content": item.content,
            }
            for item in prepared.chunks
        ]
        payload: dict[str, object] = {
            "startup": {
                "maturity": (
                    prepared.classification.category.value
                    if prepared.classification and prepared.classification.category
                    else None
                ),
            },
            "needs": needs_payload,
            "startup_evidence": evidence_payload,
            "nvidia_chunks": chunks_payload,
        }
        if not apply_char_limit:
            return payload
        text_fields: list[dict[str, object]] = [
            *needs_payload,
            *evidence_payload,
            *chunks_payload,
        ]
        text_keys = ("description", "value", "content")
        while len(compact_json(payload)) > self._config.max_context_characters:
            choices = [
                (len(value), item, key)
                for item in text_fields
                for key in text_keys
                if isinstance((value := item.get(key)), str) and len(value) > 1
            ]
            if not choices:
                break
            length, item, key = max(choices, key=lambda choice: choice[0])
            excess = len(compact_json(payload)) - self._config.max_context_characters
            item[key] = str(item[key])[: max(1, length - excess)].rstrip() or str(item[key])[:1]
        return payload

    def _parse_and_validate(
        self, raw: str, prepared: PreparedStartup
    ) -> tuple[list[StartupRecommendation] | None, list[str]]:
        try:
            output = RecommendationCandidateBatch.model_validate_json(raw)
            if len(output.candidates) > self._config.max_recommendations_per_startup:
                raise RecommendationSemanticError(["recommendation_limit_exceeded"])
            result = self._validate_batch(output.candidates, prepared)
            return result, []
        except ValidationError:
            return None, ["recommendation_schema_invalid"]
        except RecommendationSemanticError as exc:
            return None, exc.violations

    def _validate_batch(
        self, candidates: list[RecommendationCandidate], prepared: PreparedStartup
    ) -> list[StartupRecommendation]:
        violations: list[str] = []
        if len({item.technology for item in candidates}) != len(candidates):
            violations.append("recommendation_duplicate_technology")
        needs = {item.key: item for item in prepared.needs}
        evidence_by_id: dict[UUID, list[StartupRecommendationEvidence]] = {}
        for item in prepared.evidence:
            evidence_by_id.setdefault(item.source_id, []).append(item)
        chunks = {item.chunk_id: item for item in prepared.chunks}
        result: list[StartupRecommendation] = []
        for candidate in candidates:
            local = self._candidate_violations(candidate, prepared, needs, evidence_by_id, chunks)
            violations.extend(local)
            if local:
                continue
            startup_evidence = [
                item
                for source_id in candidate.startup_evidence_ids
                for item in evidence_by_id[source_id]
            ]
            nvidia_chunks = [chunks[item] for item in candidate.nvidia_chunk_ids]
            strength = self._evidence_strength(candidate, prepared)
            priority_score, priority = calculate_priority(
                candidate.need_criticality, candidate.business_relevance, strength
            )
            complexity_score, complexity = calculate_complexity(
                candidate.integration_scope,
                candidate.infrastructure_change,
                candidate.specialized_skills,
            )
            result.append(
                StartupRecommendation(
                    startup_id=prepared.profile.startup_id,
                    startup_name=prepared.profile.name,
                    maturity_considered=(
                        prepared.classification.category if prepared.classification else None
                    ),
                    technology=candidate.technology,
                    need_keys=candidate.need_keys,
                    technical_justification=candidate.technical_justification,
                    business_justification=candidate.business_justification,
                    priority=priority,
                    priority_basis=PriorityBasis(
                        need_criticality=candidate.need_criticality,
                        business_relevance=candidate.business_relevance,
                        evidence_strength=strength,
                        priority_score=priority_score,
                        evidence_ids=candidate.priority_evidence_ids,
                    ),
                    implementation_complexity=complexity,
                    complexity_basis=ComplexityBasis(
                        integration_scope=candidate.integration_scope,
                        infrastructure_change=candidate.infrastructure_change,
                        specialized_skills=candidate.specialized_skills,
                        complexity_score=complexity_score,
                        nvidia_chunk_ids=candidate.complexity_nvidia_chunk_ids,
                    ),
                    next_action=candidate.next_action,
                    startup_evidence=startup_evidence,
                    nvidia_evidence=[
                        NvidiaRecommendationEvidence(
                            chunk_id=item.chunk_id,
                            document_id=item.document_id,
                            title=item.title,
                            technology=item.technology,
                            source_url=item.source_url,
                            source_section=item.source_section,
                            start_offset=item.start_offset,
                            end_offset=item.end_offset,
                            retrieval_scores=item.scores,
                        )
                        for item in nvidia_chunks
                    ],
                )
            )
        if violations:
            raise RecommendationSemanticError(violations)
        return result

    def _candidate_violations(
        self,
        candidate: RecommendationCandidate,
        prepared: PreparedStartup,
        needs: dict[str, RecommendationNeed],
        evidence: dict[UUID, list[StartupRecommendationEvidence]],
        chunks: dict[UUID, NvidiaRetrievedChunk],
    ) -> list[str]:
        violations: list[str] = []
        if any(key not in needs for key in candidate.need_keys):
            violations.append("recommendation_need_not_allowed")
        if any(item not in evidence for item in candidate.startup_evidence_ids):
            violations.append("recommendation_startup_evidence_not_allowed")
        if any(item not in chunks for item in candidate.nvidia_chunk_ids):
            violations.append("recommendation_nvidia_chunk_not_allowed")
        if not set(candidate.priority_evidence_ids) <= set(candidate.startup_evidence_ids):
            violations.append("recommendation_priority_evidence_not_selected")
        if not set(candidate.complexity_nvidia_chunk_ids) <= set(candidate.nvidia_chunk_ids):
            violations.append("recommendation_complexity_evidence_not_selected")
        if violations:
            return violations
        selected_evidence = set(candidate.startup_evidence_ids)
        for key in candidate.need_keys:
            if not selected_evidence & set(needs[key].startup_evidence_ids):
                violations.append("recommendation_need_evidence_missing")
        if not selected_evidence & prepared.business_evidence_ids:
            violations.append("recommendation_business_evidence_missing")
        selected_chunks = [chunks[item] for item in candidate.nvidia_chunk_ids]
        if any(item.technology is not candidate.technology for item in selected_chunks):
            violations.append("recommendation_technology_mismatch")
        if not any(item.technology is candidate.technology for item in prepared.chunks):
            violations.append("recommendation_technology_not_in_context")
        evidence_text = " ".join(
            item.value
            for source_id in candidate.priority_evidence_ids
            for item in evidence[source_id]
        ).casefold()
        if candidate.need_criticality is NeedCriticality.BLOCKER and not self._contains(
            evidence_text, BLOCKER_TERMS
        ):
            violations.append("recommendation_blocker_unsupported")
        if candidate.business_relevance is BusinessRelevance.CORE and not self._contains(
            evidence_text, CORE_TERMS
        ):
            violations.append("recommendation_core_unsupported")
        strength = self._evidence_strength(candidate, prepared)
        _, priority = calculate_priority(
            candidate.need_criticality, candidate.business_relevance, strength
        )
        if candidate.priority is not priority:
            violations.append("recommendation_priority_mismatch")
        complexity_text = " ".join(
            chunks[item].content for item in candidate.complexity_nvidia_chunk_ids
        ).casefold()
        if not complexity_text:
            violations.append("recommendation_complexity_evidence_missing")
        if (
            candidate.integration_scope is IntegrationScope.CONFIGURATION_OR_API
            and not self._contains(complexity_text, API_TERMS)
        ):
            violations.append("recommendation_api_scope_unsupported")
        if (
            candidate.integration_scope is IntegrationScope.PLATFORM_OR_MIGRATION
            and not self._contains(complexity_text, PLATFORM_TERMS)
        ):
            violations.append("recommendation_platform_scope_unsupported")
        if candidate.infrastructure_change is InfrastructureChange.MAJOR and not self._contains(
            complexity_text, MAJOR_TERMS
        ):
            violations.append("recommendation_major_change_unsupported")
        if candidate.specialized_skills is SpecializedSkills.ADVANCED and not self._contains(
            complexity_text, ADVANCED_TERMS
        ):
            violations.append("recommendation_advanced_skills_unsupported")
        _, complexity = calculate_complexity(
            candidate.integration_scope,
            candidate.infrastructure_change,
            candidate.specialized_skills,
        )
        if candidate.implementation_complexity is not complexity:
            violations.append("recommendation_complexity_mismatch")
        combined_text = " ".join(
            (
                candidate.technical_justification,
                candidate.business_justification,
                candidate.next_action,
            )
        ).casefold()
        if self._contains(combined_text, PROHIBITED_PROMISES + DEPLOYED_CLAIMS):
            violations.append("recommendation_unsupported_claim")
        if self._contains(combined_text, UNSUPPORTED_ESTIMATES):
            violations.append("recommendation_unsupported_estimate")
        if (
            not self._contains(candidate.next_action.casefold(), ACTION_TERMS)
            or "nvidia" not in candidate.next_action.casefold()
        ):
            violations.append("recommendation_next_action_invalid")
        if prepared.classification is None and self._contains(combined_text, MATURITY_TERMS):
            violations.append("recommendation_maturity_not_available")
        selected_need_text = " ".join(
            needs[key].description for key in candidate.need_keys
        ).casefold()
        chunk_text = " ".join(item.content for item in selected_chunks).casefold()
        if not self._shares_meaningful_word(
            candidate.technical_justification.casefold(), selected_need_text
        ) or not self._shares_meaningful_word(
            candidate.technical_justification.casefold(), chunk_text
        ):
            violations.append("recommendation_technical_link_missing")
        business_text = " ".join(
            item.value
            for source_id in candidate.startup_evidence_ids
            for item in evidence[source_id]
            if item.field in BUSINESS_FIELDS
        ).casefold()
        if not self._shares_meaningful_word(
            candidate.business_justification.casefold(), business_text
        ):
            violations.append("recommendation_business_link_missing")
        if (
            len(candidate.technical_justification) > self._config.max_justification_length
            or len(candidate.business_justification) > self._config.max_justification_length
        ):
            violations.append("recommendation_justification_too_long")
        if len(candidate.next_action) > self._config.max_next_action_length:
            violations.append("recommendation_next_action_too_long")
        if self._incompatible(candidate, prepared.profile):
            violations.append("recommendation_explicit_constraint_conflict")
        return violations

    @staticmethod
    def _contains(text: str, terms: tuple[str, ...]) -> bool:
        return any(term in text for term in terms)

    @staticmethod
    def _shares_meaningful_word(left: str, right: str) -> bool:
        def words(text: str) -> set[str]:
            return {token for token in re.findall(r"[a-zà-ÿ0-9-]+", text) if len(token) >= 4}

        return bool(words(left) & words(right))

    @staticmethod
    def _evidence_strength(
        candidate: RecommendationCandidate, prepared: PreparedStartup
    ) -> EvidenceStrength:
        needs = {item.key: item for item in prepared.needs}
        need_ids = {
            source_id
            for key in candidate.need_keys
            if key in needs
            for source_id in needs[key].startup_evidence_ids
        }
        relevant_ids = set(candidate.startup_evidence_ids) & (
            need_ids | set(prepared.business_evidence_ids)
        )
        return (
            EvidenceStrength.CORROBORATED
            if len(relevant_ids) >= 2
            else EvidenceStrength.SINGLE_SOURCE
        )

    @staticmethod
    def _incompatible(candidate: RecommendationCandidate, profile: ValidatedStartupProfile) -> bool:
        restrictions = [*profile.infrastructure, *profile.external_dependencies]
        technology_tokens = candidate.technology.value.replace("_", " ").split()
        for fact in restrictions:
            text = fact.value.casefold()
            denies = any(
                term in text
                for term in (
                    "incompatible",
                    "does not support",
                    "não suporta",
                    "proib",
                    "cannot use",
                )
            )
            if denies and any(token in text for token in technology_tokens if len(token) > 2):
                return True
        return False

    @staticmethod
    def _sort_key(item: StartupRecommendation) -> tuple[int, int, int, str, str]:
        priority_rank = {
            RecommendationPriority.HIGH: 0,
            RecommendationPriority.MEDIUM: 1,
            RecommendationPriority.LOW: 2,
        }[item.priority]
        return (
            priority_rank,
            -item.priority_basis.priority_score,
            item.complexity_basis.complexity_score,
            item.technology.value,
            str(item.startup_id),
        )

    @staticmethod
    def _error(code: str) -> RecoverableError:
        message = (
            "The recommendation provider is unavailable."
            if code == "recommendation_unavailable"
            else "The recommendation agent could not produce a valid result."
        )
        return RecoverableError(code=code, message=message, node=NodeName.RECOMMENDATION)

    @staticmethod
    def _empty_counters() -> dict[str, float]:
        return {
            key: 0.0
            for key in (
                "input_startup_count",
                "eligible_startup_count",
                "processed_startup_count",
                "skipped_no_need_count",
                "skipped_context_count",
                "skipped_business_context_count",
                "need_count",
                "nvidia_chunk_count",
                "model_call_count",
                "repair_count",
                "invalid_batch_count",
                "accepted_count",
                "failure_count",
            )
        }

    @staticmethod
    def _patch(
        started_at: float,
        recommendations: list[StartupRecommendation],
        warnings: list[str],
        errors: list[RecoverableError],
        metrics: dict[str, float],
        counters: dict[str, float],
    ) -> AppState:
        metrics.update(
            {
                "recommendation_duration_ms": round((time.perf_counter() - started_at) * 1_000, 3),
                **{f"recommendation_{key}": value for key, value in counters.items()},
            }
        )
        logger.log(
            logging.WARNING if counters["failure_count"] else logging.INFO,
            "recommendation_completed",
            extra={
                "node": NodeName.RECOMMENDATION,
                "prompt_version": PROMPT_VERSION,
                "status": "error" if counters["failure_count"] else "completed",
                "duration_ms": metrics["recommendation_duration_ms"],
                "startup_count": counters["processed_startup_count"],
                "recommendation_count": counters["accepted_count"],
                "failure_count": counters["failure_count"],
            },
        )
        return AppState(
            recommendations=recommendations,
            warnings=list(dict.fromkeys(warnings)),
            errors=errors,
            metrics=metrics,
        )


def create_recommendation_agent(
    *, registry: ModelRegistry, config: RecommendationConfig
) -> RecommendationAgent:
    return RecommendationAgent(
        model=registry.resolve(NodeName.RECOMMENDATION),
        config=config,
    )
