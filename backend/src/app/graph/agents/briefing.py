from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.application.contracts.briefing import (
    BriefingClassificationSignal,
    BriefingFact,
    BriefingMissingSection,
    BriefingNarrativeOutput,
    BriefingNvidiaCitation,
    BriefingRecommendation,
    BriefingStartupCitation,
    BriefingStatement,
    BriefingStatementKind,
    BriefingTechnicalGap,
    StartupBriefing,
)
from app.application.contracts.evidence_validation import (
    ValidatedClassification,
    ValidatedStartupProfile,
)
from app.application.contracts.extraction import ExtractedFact, ExtractionSource, ProfileField
from app.application.contracts.knowledge_ingestion import NvidiaTechnology
from app.application.contracts.nvidia_rag import NvidiaRetrievedChunk, NvidiaStartupContext
from app.application.contracts.recommendation import (
    NvidiaRecommendationEvidence,
    StartupRecommendation,
    StartupRecommendationEvidence,
)
from app.application.ports.providers import ChatMessage, ChatModel
from app.core.config import BriefingConfig
from app.domain.models import AIMaturity, RecoverableError, TechnicalGap
from app.graph.model_policy import ModelRegistry
from app.graph.nodes import NodeName
from app.graph.prompts.briefing import PROMPT_VERSION, build_messages, build_repair_message
from app.graph.prompts.json_format import compact_json
from app.graph.state import AppState

logger = logging.getLogger(__name__)

BUSINESS_FIELDS = (
    ProfileField.PRODUCT,
    ProfileField.BUSINESS_MODEL,
    ProfileField.SECTOR,
    ProfileField.TARGET_AUDIENCE,
    ProfileField.AI_USE_CASES,
)
STACK_FIELDS = (
    ProfileField.TECHNOLOGIES,
    ProfileField.INFRASTRUCTURE,
    ProfileField.EXTERNAL_DEPENDENCIES,
)
PROHIBITED_TERMS = (
    "guarantee",
    "garantia",
    "guaranteed",
    "roi certo",
    "retorno garantido",
    "admission guaranteed",
    "ingresso garantido",
    "eligible for inception",
    "elegível ao inception",
    "price",
    "preço",
    "deadline",
    "prazo de",
)
MATURITY_TERMS = ("maturity", "maturidade", "ai-native", "ai-enabled", "non-ai")


@dataclass(slots=True)
class _StartupCitationData:
    startup_id: UUID
    source_id: UUID
    source_url: str
    fields: list[ProfileField]
    values: list[str]


@dataclass(frozen=True, slots=True)
class PreparedBriefing:
    startup_id: UUID
    startup_name: str
    business_facts: list[BriefingFact]
    ai_maturity: AIMaturity | None
    ai_maturity_citation_ids: list[str]
    classification_signals: list[BriefingClassificationSignal]
    identified_stack: list[BriefingFact]
    technical_gaps: list[BriefingTechnicalGap]
    recommendations: list[BriefingRecommendation]
    startup_citations: list[BriefingStartupCitation]
    nvidia_citations: list[BriefingNvidiaCitation]
    startup_text: dict[str, str]
    nvidia_text: dict[str, str]
    missing_sections: list[BriefingMissingSection]
    truncated: bool


class BriefingSemanticError(ValueError):
    def __init__(self, violations: list[str]) -> None:
        super().__init__("invalid briefing narrative")
        self.violations = list(dict.fromkeys(violations))


class BriefingAgent:
    def __init__(self, *, model: ChatModel, config: BriefingConfig) -> None:
        self._model = model
        self._config = config

    async def __call__(self, state: AppState) -> AppState:
        started_at = time.perf_counter()
        warnings = list(state.get("warnings", []))
        errors = list(state.get("errors", []))
        briefings = list(state.get("briefings", []))
        metrics = dict(state.get("metrics", {}))
        counters = self._empty_counters()
        recommendations = state.get("recommendations", [])
        counters["input_recommendation_count"] = float(len(recommendations))
        if not recommendations:
            warnings.append("briefing_no_recommendations")
            return self._patch(started_at, briefings, warnings, errors, metrics, counters)

        grouped: dict[UUID, list[StartupRecommendation]] = {}
        for recommendation in recommendations:
            grouped.setdefault(recommendation.startup_id, []).append(recommendation)
        startup_groups = list(grouped.items())
        if len(startup_groups) > self._config.max_startups:
            startup_groups = startup_groups[: self._config.max_startups]
            warnings.append("briefing_context_truncated")
            counters["truncation_count"] += 1
        counters["eligible_startup_count"] = float(len(startup_groups))

        profiles = {item.startup_id: item for item in state.get("validated_profiles", [])}
        classifications = {
            item.startup_id: item for item in state.get("validated_classifications", [])
        }
        contexts = {item.startup_id: item for item in state.get("nvidia_contexts", [])}

        for startup_id, startup_recommendations in startup_groups:
            prepared, local_warnings = self._prepare(
                startup_id=startup_id,
                recommendations=startup_recommendations,
                profile=profiles.get(startup_id),
                classification=classifications.get(startup_id),
                context=contexts.get(startup_id),
                gaps=state.get("technical_gaps", []),
            )
            warnings.extend(local_warnings)
            if prepared is None:
                counters["failure_count"] += 1
                continue
            if prepared.truncated:
                warnings.append("briefing_context_truncated")
                counters["truncation_count"] += 1
            if not self._inception_ids(prepared):
                warnings.append("briefing_inception_context_unavailable")
            counters["processed_startup_count"] += 1
            raw_candidate = ""
            prompt_context, prompt_truncated = self._prompt_context(prepared)
            if prompt_truncated:
                warnings.append("briefing_context_truncated")
                counters["truncation_count"] += 1
            system_prompt, user_prompt = build_messages(prompt_context)
            try:
                counters["model_call_count"] += 1
                raw_candidate = await self._model.complete(
                    [
                        ChatMessage(role="system", content=system_prompt),
                        ChatMessage(role="user", content=user_prompt),
                    ]
                )
                narrative, violations = self._parse_and_validate(raw_candidate, prepared)
                attempt = 0
                while narrative is None and attempt < self._config.max_repair_attempts:
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
                                    startup_citation_ids=[
                                        item.citation_id for item in prepared.startup_citations
                                    ],
                                    nvidia_citation_ids=[
                                        item.citation_id for item in prepared.nvidia_citations
                                    ],
                                    inception_citation_ids=sorted(self._inception_ids(prepared)),
                                ),
                            ),
                        ]
                    )
                    narrative, violations = self._parse_and_validate(raw_candidate, prepared)
            except Exception:
                errors.append(self._error("briefing_unavailable"))
                counters["failure_count"] += 1
                continue
            if narrative is None:
                errors.append(self._error("briefing_invalid_output"))
                counters["invalid_batch_count"] += 1
                counters["failure_count"] += 1
                continue
            briefing, markdown_truncated = self._build_final(prepared, narrative)
            if markdown_truncated:
                warnings.append("briefing_context_truncated")
                counters["truncation_count"] += 1
            briefings.append(briefing)
            counters["statement_count"] += float(
                len(narrative.executive_summary)
                + len(narrative.inception_opportunities)
                + len(narrative.uncertainties_and_gaps)
            )
            counters["accepted_briefing_count"] += 1

        return self._patch(started_at, briefings, warnings, errors, metrics, counters)

    def _prepare(
        self,
        *,
        startup_id: UUID,
        recommendations: list[StartupRecommendation],
        profile: ValidatedStartupProfile | None,
        classification: ValidatedClassification | None,
        context: NvidiaStartupContext | None,
        gaps: list[TechnicalGap],
    ) -> tuple[PreparedBriefing | None, list[str]]:
        warnings: list[str] = []
        truncated = False
        if profile is None:
            warnings.append("briefing_profile_unavailable")
        if classification is None:
            warnings.append("briefing_classification_unavailable")

        bounded_recommendations = recommendations[: self._config.max_recommendations]
        truncated |= len(bounded_recommendations) != len(recommendations)
        startup_data: dict[UUID, _StartupCitationData] = {}

        def add_startup_source(
            source: ExtractionSource | StartupRecommendationEvidence,
            *,
            field: ProfileField | None,
            value: str,
        ) -> None:
            if source.startup_id != startup_id:
                return
            current = startup_data.get(source.source_id)
            if current is None:
                startup_data[source.source_id] = _StartupCitationData(
                    startup_id=startup_id,
                    source_id=source.source_id,
                    source_url=source.source_url,
                    fields=[field] if field else [],
                    values=[value],
                )
                return
            if current.source_url != source.source_url:
                warnings.append("briefing_citation_unavailable")
                return
            if field is not None and field not in current.fields:
                current.fields.append(field)
            if value not in current.values:
                current.values.append(value)

        for recommendation in bounded_recommendations:
            for evidence in recommendation.startup_evidence:
                add_startup_source(evidence, field=evidence.field, value=evidence.value)
        if profile is not None:
            for field in ProfileField:
                for fact in self._facts(profile, field):
                    for source in fact.sources:
                        add_startup_source(source, field=field, value=fact.value)
        if classification is not None:
            for signal in classification.signals:
                for source in signal.sources:
                    add_startup_source(source, field=None, value=signal.description)
            for source in classification.evidence_references:
                add_startup_source(
                    source,
                    field=None,
                    value=classification.justification,
                )

        startup_items = list(startup_data.values())
        if len(startup_items) > self._config.max_citations:
            startup_items = startup_items[: self._config.max_citations]
            truncated = True
        startup_citations = [
            BriefingStartupCitation(
                citation_id=f"S{index}",
                startup_id=item.startup_id,
                source_id=item.source_id,
                source_url=item.source_url,
                fields=item.fields,
                values=item.values,
            )
            for index, item in enumerate(startup_items, start=1)
        ]
        startup_id_map = {item.source_id: item.citation_id for item in startup_citations}

        nvidia_evidence: list[tuple[NvidiaRecommendationEvidence | NvidiaRetrievedChunk, str]] = []
        seen_chunks: set[UUID] = set()

        def add_nvidia(
            item: NvidiaRecommendationEvidence | NvidiaRetrievedChunk, text: str
        ) -> None:
            if item.chunk_id not in seen_chunks:
                seen_chunks.add(item.chunk_id)
                nvidia_evidence.append((item, text))

        for recommendation in bounded_recommendations:
            for nvidia_item in recommendation.nvidia_evidence:
                add_nvidia(
                    nvidia_item,
                    " ".join(
                        (
                            recommendation.technical_justification,
                            recommendation.business_justification,
                        )
                    ),
                )
        context_chunks = (
            [item for item in context.chunks if item.startup_id == startup_id]
            if context is not None and context.startup_id == startup_id
            else []
        )
        context_chunks.sort(
            key=lambda item: item.technology is not NvidiaTechnology.NVIDIA_INCEPTION
        )
        for chunk in context_chunks:
            add_nvidia(chunk, chunk.content)
        if len(nvidia_evidence) > self._config.max_citations:
            nvidia_evidence = nvidia_evidence[: self._config.max_citations]
            truncated = True
        nvidia_citations = [
            self._nvidia_citation(item, index)
            for index, (item, _) in enumerate(nvidia_evidence, start=1)
        ]
        nvidia_id_map = {item.chunk_id: item.citation_id for item in nvidia_citations}

        business_facts = self._section_facts(
            profile,
            bounded_recommendations,
            BUSINESS_FIELDS,
            startup_id_map,
            warnings,
        )
        identified_stack = self._section_facts(
            profile,
            bounded_recommendations,
            STACK_FIELDS,
            startup_id_map,
            warnings,
        )
        business_facts, changed = self._bound(business_facts, self._config.max_facts_per_section)
        truncated |= changed
        identified_stack, changed = self._bound(
            identified_stack, self._config.max_facts_per_section
        )
        truncated |= changed

        maturity = classification.category if classification is not None else None
        maturity_sources = (
            [
                *classification.evidence_references,
                *(source for signal in classification.signals for source in signal.sources),
            ]
            if classification is not None
            else []
        )
        maturity_ids = list(
            dict.fromkeys(
                startup_id_map[source.source_id]
                for source in maturity_sources
                if source.source_id in startup_id_map
            )
        )
        if maturity is not None and not maturity_ids:
            maturity = None
            warnings.append("briefing_citation_unavailable")

        signals: list[BriefingClassificationSignal] = []
        if classification is not None:
            for signal in classification.signals:
                citation_ids = list(
                    dict.fromkeys(
                        startup_id_map[source.source_id]
                        for source in signal.sources
                        if source.source_id in startup_id_map
                    )
                )
                if citation_ids:
                    signals.append(
                        BriefingClassificationSignal(
                            type=signal.type,
                            description=signal.description,
                            citation_ids=citation_ids,
                        )
                    )
                else:
                    warnings.append("briefing_citation_unavailable")
        signals, changed = self._bound(signals, self._config.max_signals)
        truncated |= changed

        technical_gaps: list[BriefingTechnicalGap] = []
        for gap in gaps:
            citation_ids = list(
                dict.fromkeys(
                    startup_id_map[source_id]
                    for source_id in gap.evidence_ids
                    if source_id in startup_id_map
                )
            )
            if citation_ids:
                technical_gaps.append(
                    BriefingTechnicalGap(
                        name=gap.name,
                        description=gap.description,
                        citation_ids=citation_ids,
                    )
                )
            else:
                warnings.append("briefing_citation_unavailable")
        technical_gaps, changed = self._bound(technical_gaps, self._config.max_gaps)
        truncated |= changed

        briefing_recommendations: list[BriefingRecommendation] = []
        for recommendation in bounded_recommendations:
            startup_ids = list(
                dict.fromkeys(
                    startup_id_map[item.source_id]
                    for item in recommendation.startup_evidence
                    if item.source_id in startup_id_map
                )
            )
            nvidia_ids = list(
                dict.fromkeys(
                    nvidia_id_map[item.chunk_id]
                    for item in recommendation.nvidia_evidence
                    if item.chunk_id in nvidia_id_map
                )
            )
            priority_ids = list(
                dict.fromkeys(
                    startup_id_map[item]
                    for item in recommendation.priority_basis.evidence_ids
                    if item in startup_id_map
                )
            )
            complexity_ids = list(
                dict.fromkeys(
                    nvidia_id_map[item]
                    for item in recommendation.complexity_basis.nvidia_chunk_ids
                    if item in nvidia_id_map
                )
            )
            if not startup_ids or not nvidia_ids or not priority_ids or not complexity_ids:
                warnings.append("briefing_citation_unavailable")
                continue
            briefing_recommendations.append(
                BriefingRecommendation(
                    technology=recommendation.technology,
                    need_keys=recommendation.need_keys,
                    technical_justification=recommendation.technical_justification,
                    business_justification=recommendation.business_justification,
                    priority=recommendation.priority,
                    implementation_complexity=recommendation.implementation_complexity,
                    next_action=recommendation.next_action,
                    startup_citation_ids=startup_ids,
                    nvidia_citation_ids=nvidia_ids,
                    priority_citation_ids=priority_ids,
                    complexity_citation_ids=complexity_ids,
                )
            )
        if not briefing_recommendations or not startup_citations or not nvidia_citations:
            warnings.append("briefing_citation_unavailable")
            return None, warnings

        missing = []
        if profile is None:
            missing.append(BriefingMissingSection.PROFILE)
        if not business_facts:
            missing.append(BriefingMissingSection.BUSINESS)
        if maturity is None:
            missing.append(BriefingMissingSection.AI_MATURITY)
        if not signals:
            missing.append(BriefingMissingSection.SIGNALS)
        if not identified_stack:
            missing.append(BriefingMissingSection.STACK)
        if not technical_gaps:
            missing.append(BriefingMissingSection.TECHNICAL_GAPS)
        if not any(
            item.technology is NvidiaTechnology.NVIDIA_INCEPTION for item in nvidia_citations
        ):
            missing.append(BriefingMissingSection.INCEPTION_OPPORTUNITIES)

        prepared = PreparedBriefing(
            startup_id=startup_id,
            startup_name=bounded_recommendations[0].startup_name,
            business_facts=business_facts,
            ai_maturity=maturity,
            ai_maturity_citation_ids=maturity_ids,
            classification_signals=signals,
            identified_stack=identified_stack,
            technical_gaps=technical_gaps,
            recommendations=briefing_recommendations,
            startup_citations=startup_citations,
            nvidia_citations=nvidia_citations,
            startup_text={item.citation_id: " ".join(item.values) for item in startup_citations},
            nvidia_text={
                citation.citation_id: text
                for citation, (_, text) in zip(nvidia_citations, nvidia_evidence, strict=True)
            },
            missing_sections=missing,
            truncated=truncated,
        )
        return prepared, warnings

    @staticmethod
    def _facts(profile: ValidatedStartupProfile, field: ProfileField) -> list[ExtractedFact]:
        value = getattr(profile, field.value)
        return value if isinstance(value, list) else ([value] if value is not None else [])

    def _section_facts(
        self,
        profile: ValidatedStartupProfile | None,
        recommendations: list[StartupRecommendation],
        fields: tuple[ProfileField, ...],
        citation_map: dict[UUID, str],
        warnings: list[str],
    ) -> list[BriefingFact]:
        candidates: list[tuple[ProfileField, str, list[UUID]]] = []
        if profile is not None:
            for field in fields:
                for fact in self._facts(profile, field):
                    candidates.append(
                        (field, fact.value, [source.source_id for source in fact.sources])
                    )
        else:
            seen: set[tuple[ProfileField, str]] = set()
            for recommendation in recommendations:
                for evidence in recommendation.startup_evidence:
                    key = (evidence.field, evidence.value)
                    if evidence.field in fields and key not in seen:
                        seen.add(key)
                        candidates.append((evidence.field, evidence.value, [evidence.source_id]))
        result: list[BriefingFact] = []
        for field, value, source_ids in candidates:
            citation_ids = list(
                dict.fromkeys(citation_map[item] for item in source_ids if item in citation_map)
            )
            if citation_ids:
                result.append(BriefingFact(field=field, value=value, citation_ids=citation_ids))
            else:
                warnings.append("briefing_citation_unavailable")
        return result

    @staticmethod
    def _nvidia_citation(
        item: NvidiaRecommendationEvidence | NvidiaRetrievedChunk, index: int
    ) -> BriefingNvidiaCitation:
        scores = (
            item.retrieval_scores if isinstance(item, NvidiaRecommendationEvidence) else item.scores
        )
        return BriefingNvidiaCitation(
            citation_id=f"N{index}",
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            technology=item.technology,
            title=item.title,
            source_url=item.source_url,
            source_section=item.source_section,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            retrieval_scores=scores,
        )

    @staticmethod
    def _bound[T](items: list[T], limit: int) -> tuple[list[T], bool]:
        return items[:limit], len(items) > limit

    def _prompt_context(self, prepared: PreparedBriefing) -> tuple[dict[str, object], bool]:
        payload: dict[str, object] = {
            "startup": {
                "name": prepared.startup_name,
                "ai_maturity": (
                    prepared.ai_maturity.value if prepared.ai_maturity is not None else None
                ),
            },
            "business_facts": [item.model_dump(mode="json") for item in prepared.business_facts],
            "classification_signals": [
                item.model_dump(mode="json") for item in prepared.classification_signals
            ],
            "identified_stack": [
                item.model_dump(mode="json") for item in prepared.identified_stack
            ],
            "technical_gaps": [item.model_dump(mode="json") for item in prepared.technical_gaps],
            "recommendations": [item.model_dump(mode="json") for item in prepared.recommendations],
            "startup_citations": prepared.startup_text,
            "nvidia_citations": [
                {
                    "citation_id": item.citation_id,
                    "technology": item.technology.value,
                    "content": prepared.nvidia_text[item.citation_id],
                }
                for item in prepared.nvidia_citations
            ],
            "missing_sections": [item.value for item in prepared.missing_sections],
        }
        truncated = len(compact_json(payload)) > self._config.max_context_characters
        return self._truncate_payload(payload), truncated

    def _truncate_payload(self, payload: dict[str, object]) -> dict[str, object]:
        if len(compact_json(payload)) <= self._config.max_context_characters:
            return payload
        strings: list[tuple[dict[str, object], str]] = []

        def visit(value: object) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if isinstance(child, str) and key not in {
                        "citation_id",
                        "technology",
                        "field",
                        "kind",
                        "type",
                    }:
                        strings.append((value, key))
                    else:
                        visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(payload)
        while len(compact_json(payload)) > self._config.max_context_characters:
            choices = [
                (len(str(container[key])), container, key)
                for container, key in strings
                if len(str(container[key])) > 1
            ]
            if not choices:
                break
            length, container, key = max(choices, key=lambda item: item[0])
            excess = len(compact_json(payload)) - self._config.max_context_characters
            original = str(container[key])
            container[key] = original[: max(1, length - excess)].rstrip() or original[:1]
        return payload

    def _parse_and_validate(
        self, raw: str, prepared: PreparedBriefing
    ) -> tuple[BriefingNarrativeOutput | None, list[str]]:
        try:
            output = BriefingNarrativeOutput.model_validate_json(raw)
            count = (
                len(output.executive_summary)
                + len(output.inception_opportunities)
                + len(output.uncertainties_and_gaps)
            )
            if count > self._config.max_statements:
                raise BriefingSemanticError(["briefing_statement_limit_exceeded"])
            violations = self._narrative_violations(output, prepared)
            if violations:
                raise BriefingSemanticError(violations)
            return output, []
        except ValidationError:
            return None, ["briefing_schema_invalid"]
        except BriefingSemanticError as exc:
            return None, exc.violations

    def _narrative_violations(
        self, output: BriefingNarrativeOutput, prepared: PreparedBriefing
    ) -> list[str]:
        violations: list[str] = []
        startup_ids = set(prepared.startup_text)
        nvidia_ids = set(prepared.nvidia_text)
        inception_ids = self._inception_ids(prepared)
        all_ids = startup_ids | nvidia_ids
        statements = [
            *output.executive_summary,
            *output.inception_opportunities,
            *output.uncertainties_and_gaps,
        ]
        for statement in statements:
            selected = set(statement.citation_ids)
            if not selected <= all_ids:
                violations.append("briefing_citation_not_allowed")
                continue
            if len(statement.text) > self._config.max_statement_length:
                violations.append("briefing_statement_too_long")
            if any(term in statement.text.casefold() for term in PROHIBITED_TERMS):
                violations.append("briefing_unsupported_claim")
            if prepared.ai_maturity is None and any(
                term in statement.text.casefold() for term in MATURITY_TERMS
            ):
                violations.append("briefing_maturity_not_available")
            if statement.kind is BriefingStatementKind.CONFIRMED_FACT and selected & nvidia_ids:
                violations.append("briefing_confirmed_fact_source_invalid")
            if statement.kind is BriefingStatementKind.SUPPORTED_INFERENCE and not (
                selected & startup_ids and selected & nvidia_ids
            ):
                violations.append("briefing_inference_requires_dual_evidence")
            cited_text = " ".join(
                prepared.startup_text.get(item, prepared.nvidia_text.get(item, ""))
                for item in statement.citation_ids
            )
            if not self._shares_word(statement.text, cited_text):
                violations.append("briefing_statement_not_grounded")
        for statement in output.inception_opportunities:
            if statement.kind is not BriefingStatementKind.SUPPORTED_INFERENCE:
                violations.append("briefing_inception_must_be_inference")
            if not set(statement.citation_ids) & inception_ids:
                violations.append("briefing_inception_source_missing")
        if any(
            item.kind not in {BriefingStatementKind.UNCERTAINTY, BriefingStatementKind.GAP}
            for item in output.uncertainties_and_gaps
        ):
            violations.append("briefing_uncertainty_kind_invalid")
        return list(dict.fromkeys(violations))

    @staticmethod
    def _shares_word(left: str, right: str) -> bool:
        def words(value: str) -> set[str]:
            return {
                item for item in re.findall(r"[a-zà-ÿ0-9-]+", value.casefold()) if len(item) >= 4
            }

        return bool(words(left) & words(right))

    @staticmethod
    def _inception_ids(prepared: PreparedBriefing) -> set[str]:
        return {
            item.citation_id
            for item in prepared.nvidia_citations
            if item.technology is NvidiaTechnology.NVIDIA_INCEPTION
        }

    def _build_final(
        self, prepared: PreparedBriefing, narrative: BriefingNarrativeOutput
    ) -> tuple[StartupBriefing, bool]:
        values: dict[str, object] = {
            "startup_id": prepared.startup_id,
            "startup_name": prepared.startup_name,
            "business_facts": prepared.business_facts,
            "ai_maturity": prepared.ai_maturity,
            "ai_maturity_citation_ids": prepared.ai_maturity_citation_ids,
            "classification_signals": prepared.classification_signals,
            "identified_stack": prepared.identified_stack,
            "technical_gaps": prepared.technical_gaps,
            "recommendations": prepared.recommendations,
            "executive_summary": [
                BriefingStatement.model_validate(item.model_dump())
                for item in narrative.executive_summary
            ],
            "inception_opportunities": [
                BriefingStatement.model_validate(item.model_dump())
                for item in narrative.inception_opportunities
            ],
            "uncertainties_and_gaps": [
                BriefingStatement.model_validate(item.model_dump())
                for item in narrative.uncertainties_and_gaps
            ],
            "startup_citations": prepared.startup_citations,
            "nvidia_citations": prepared.nvidia_citations,
            "missing_sections": prepared.missing_sections,
        }
        markdown = self._render_markdown(values)
        truncated = len(markdown) > self._config.max_markdown_characters
        if truncated:
            suffix = "\n\n> Conteúdo truncado pelo limite configurado."
            markdown = (
                markdown[: self._config.max_markdown_characters - len(suffix)].rstrip() + suffix
            )
        return StartupBriefing(**values, markdown=markdown), truncated

    def _render_markdown(self, values: dict[str, Any]) -> str:
        lines = [f"# Briefing executivo — {self._safe(str(values['startup_name']))}"]
        lines.extend(
            ("", "## Identificação", f"- Startup: {self._safe(str(values['startup_name']))}")
        )
        self._fact_section(lines, "Resumo do negócio", values["business_facts"])
        lines.extend(("", "## Maturidade de IA"))
        maturity = values["ai_maturity"]
        maturity_ids = values["ai_maturity_citation_ids"]
        maturity_value = getattr(maturity, "value", "Não disponível")
        lines.append(f"- {maturity_value} {self._markers(maturity_ids)}".rstrip())
        lines.extend(("", "### Sinais"))
        signals = values["classification_signals"]
        if signals:
            for item in signals:
                lines.append(f"- {self._safe(item.description)} {self._markers(item.citation_ids)}")
        else:
            lines.append("- Não disponível.")
        self._fact_section(lines, "Stack identificada", values["identified_stack"])
        lines.extend(("", "## Gaps técnicos"))
        gaps = values["technical_gaps"]
        if gaps:
            for item in gaps:
                lines.append(
                    f"- **{self._safe(item.name)}:** {self._safe(item.description)} "
                    f"{self._markers(item.citation_ids)}"
                )
        else:
            lines.append("- Não disponível.")
        lines.extend(("", "## Tecnologias NVIDIA recomendadas"))
        for item in values["recommendations"]:
            markers = self._markers(item.startup_citation_ids + item.nvidia_citation_ids)
            priority_markers = self._markers(item.priority_citation_ids)
            complexity_markers = self._markers(item.complexity_citation_ids)
            technical = self._safe(item.technical_justification)
            business = self._safe(item.business_justification)
            lines.extend(
                (
                    f"### {item.technology.value} {markers}",
                    f"- Justificativa técnica: {technical} {markers}",
                    f"- Justificativa de negócio: {business} {markers}",
                    f"- Prioridade: {item.priority.value} {priority_markers}",
                    f"- Complexidade: {item.implementation_complexity.value} {complexity_markers}",
                    f"- Ação sugerida: {self._safe(item.next_action)} {markers}",
                )
            )
        self._statement_section(
            lines, "Possíveis oportunidades NVIDIA Inception", values["inception_opportunities"]
        )
        self._statement_section(lines, "Síntese executiva", values["executive_summary"])
        self._statement_section(lines, "Incertezas e lacunas", values["uncertainties_and_gaps"])
        lines.extend(("", "## Fontes"))
        for item in values["startup_citations"]:
            lines.append(f"- [{item.citation_id}] Startup: {item.source_url}")
        for item in values["nvidia_citations"]:
            lines.append(
                f"- [{item.citation_id}] NVIDIA — {self._safe(item.title)}: {item.source_url}"
            )
        return "\n".join(lines).strip()

    def _fact_section(self, lines: list[str], title: str, facts: Any) -> None:
        lines.extend(("", f"## {title}"))
        if facts:
            for item in facts:
                lines.append(
                    f"- {item.field.value}: {self._safe(item.value)} "
                    f"{self._markers(item.citation_ids)}"
                )
        else:
            lines.append("- Não disponível.")

    def _statement_section(self, lines: list[str], title: str, statements: Any) -> None:
        lines.extend(("", f"## {title}"))
        if statements:
            for item in statements:
                lines.append(
                    f"- **{item.kind.value}:** {self._safe(item.text)} "
                    f"{self._markers(item.citation_ids)}"
                )
        else:
            lines.append("- Não identificado com as evidências disponíveis.")

    @staticmethod
    def _safe(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().replace("[", "\\[").replace("]", "\\]")

    @staticmethod
    def _markers(citation_ids: Any) -> str:
        return " ".join(f"[{item}]" for item in citation_ids)

    @staticmethod
    def _error(code: str) -> RecoverableError:
        message = (
            "The briefing provider is unavailable."
            if code == "briefing_unavailable"
            else "The briefing agent could not produce a valid result."
        )
        return RecoverableError(code=code, message=message, node=NodeName.BRIEFING)

    @staticmethod
    def _empty_counters() -> dict[str, float]:
        return {
            key: 0.0
            for key in (
                "input_recommendation_count",
                "eligible_startup_count",
                "processed_startup_count",
                "model_call_count",
                "repair_count",
                "invalid_batch_count",
                "statement_count",
                "accepted_briefing_count",
                "truncation_count",
                "failure_count",
            )
        }

    @staticmethod
    def _patch(
        started_at: float,
        briefings: list[StartupBriefing],
        warnings: list[str],
        errors: list[RecoverableError],
        metrics: dict[str, float],
        counters: dict[str, float],
    ) -> AppState:
        metrics.update(
            {
                "briefing_duration_ms": round((time.perf_counter() - started_at) * 1_000, 3),
                **{f"briefing_{key}": value for key, value in counters.items()},
            }
        )
        logger.log(
            logging.WARNING if counters["failure_count"] else logging.INFO,
            "briefing_completed",
            extra={
                "node": NodeName.BRIEFING,
                "prompt_version": PROMPT_VERSION,
                "status": "error" if counters["failure_count"] else "completed",
                "duration_ms": metrics["briefing_duration_ms"],
                "startup_count": counters["processed_startup_count"],
                "briefing_count": counters["accepted_briefing_count"],
                "failure_count": counters["failure_count"],
            },
        )
        return AppState(
            briefings=briefings,
            warnings=list(dict.fromkeys(warnings)),
            errors=errors,
            metrics=metrics,
        )


def create_briefing_agent(*, registry: ModelRegistry, config: BriefingConfig) -> BriefingAgent:
    return BriefingAgent(model=registry.resolve(NodeName.BRIEFING), config=config)
