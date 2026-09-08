from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from app.application.contracts.evidence_validation import (
    ValidatedClassification,
    ValidatedStartupProfile,
)
from app.application.contracts.extraction import ExtractedFact, ProfileField
from app.application.contracts.knowledge_ingestion import NvidiaTechnology
from app.application.contracts.nvidia_rag import (
    NvidiaContextGap,
    NvidiaContextStatus,
    NvidiaContextSufficiency,
    NvidiaQueryTrace,
    NvidiaRankingMode,
    NvidiaRetrievalScores,
    NvidiaRetrievedChunk,
    NvidiaStartupContext,
)
from app.application.ports.knowledge import (
    KnowledgeLexicalSearch,
    KnowledgeRetrievalRepository,
    KnowledgeSearchHit,
    KnowledgeVectorSearch,
)
from app.application.ports.providers import EmbeddingModel, RankedDocument, Reranker
from app.core.config import NvidiaRagConfig
from app.domain.models import KnowledgeChunk, KnowledgeDocument, RecoverableError, TechnicalGap
from app.graph.nodes import NodeName
from app.graph.state import AppState

QUERY_FIELD_ORDER = (
    ProfileField.TECHNICAL_NEEDS,
    ProfileField.AI_USE_CASES,
    ProfileField.TECHNOLOGIES,
    ProfileField.INFRASTRUCTURE,
    ProfileField.EXTERNAL_DEPENDENCIES,
    ProfileField.PRODUCT,
    ProfileField.SECTOR,
    ProfileField.TARGET_AUDIENCE,
    ProfileField.BUSINESS_MODEL,
    ProfileField.CLAIMS,
)
TECHNICAL_QUERY_FIELDS = {
    ProfileField.TECHNICAL_NEEDS,
    ProfileField.AI_USE_CASES,
    ProfileField.TECHNOLOGIES,
    ProfileField.INFRASTRUCTURE,
    ProfileField.EXTERNAL_DEPENDENCIES,
}


@dataclass(frozen=True, slots=True)
class QueryPart:
    field: str
    value: str
    evidence_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class RankedHit:
    chunk_id: UUID
    raw_score: float
    rank: int
    rank_score: float


@dataclass(frozen=True, slots=True)
class FusedHit:
    chunk_id: UUID
    vector: RankedHit | None
    lexical: RankedHit | None
    vector_weight: float
    lexical_weight: float
    hybrid_score: float


def is_usable_profile(profile: ValidatedStartupProfile) -> bool:
    return any(
        getattr(profile, field.value) not in (None, []) for field in QUERY_FIELD_ORDER
    ) or bool(profile.claims)


def normalized_rank_score(rank: int, rrf_k: int) -> float:
    return (rrf_k + 1) / (rrf_k + rank)


def rank_search_hits(
    hits: list[KnowledgeSearchHit],
    *,
    chunks_by_id: dict[UUID, KnowledgeChunk],
    rrf_k: int,
    require_positive_score: bool = False,
) -> list[RankedHit]:
    best_by_id: dict[UUID, float] = {}
    for hit in hits:
        if hit.chunk_id not in chunks_by_id or not math.isfinite(hit.score):
            continue
        if require_positive_score and hit.score <= 0:
            continue
        previous = best_by_id.get(hit.chunk_id)
        if previous is None or hit.score > previous:
            best_by_id[hit.chunk_id] = hit.score

    def stable_key(item: tuple[UUID, float]) -> tuple[float, UUID, int, UUID]:
        chunk = chunks_by_id[item[0]]
        return (-item[1], chunk.document_id, chunk.chunk_index, chunk.id)

    ordered = sorted(best_by_id.items(), key=stable_key)
    return [
        RankedHit(
            chunk_id=chunk_id,
            raw_score=score,
            rank=rank,
            rank_score=normalized_rank_score(rank, rrf_k),
        )
        for rank, (chunk_id, score) in enumerate(ordered, start=1)
    ]


def fuse_ranked_hits(
    vector_hits: list[RankedHit],
    lexical_hits: list[RankedHit],
    *,
    vector_available: bool,
    lexical_available: bool,
    vector_weight: float,
    lexical_weight: float,
    chunks_by_id: dict[UUID, KnowledgeChunk],
    limit: int,
) -> list[FusedHit]:
    available_weight = (vector_weight if vector_available else 0) + (
        lexical_weight if lexical_available else 0
    )
    if available_weight <= 0:
        return []
    effective_vector_weight = vector_weight / available_weight if vector_available else 0.0
    effective_lexical_weight = lexical_weight / available_weight if lexical_available else 0.0
    vector_by_id = {item.chunk_id: item for item in vector_hits}
    lexical_by_id = {item.chunk_id: item for item in lexical_hits}
    fused = []
    for chunk_id in vector_by_id.keys() | lexical_by_id.keys():
        vector = vector_by_id.get(chunk_id)
        lexical = lexical_by_id.get(chunk_id)
        score = effective_vector_weight * (vector.rank_score if vector else 0) + (
            effective_lexical_weight * (lexical.rank_score if lexical else 0)
        )
        fused.append(
            FusedHit(
                chunk_id=chunk_id,
                vector=vector,
                lexical=lexical,
                vector_weight=effective_vector_weight,
                lexical_weight=effective_lexical_weight,
                hybrid_score=score,
            )
        )

    def stable_key(item: FusedHit) -> tuple[float, int, UUID, int, UUID]:
        chunk = chunks_by_id[item.chunk_id]
        ranks = [hit.rank for hit in (item.vector, item.lexical) if hit is not None]
        return (
            -item.hybrid_score,
            min(ranks),
            chunk.document_id,
            chunk.chunk_index,
            chunk.id,
        )

    return sorted(fused, key=stable_key)[:limit]


class NvidiaRagAgent:
    def __init__(
        self,
        *,
        repository: KnowledgeRetrievalRepository,
        vector_search: KnowledgeVectorSearch,
        lexical_search: KnowledgeLexicalSearch,
        embedding_model: EmbeddingModel | None,
        reranker: Reranker | None,
        config: NvidiaRagConfig,
        embedding_dimension: int,
    ) -> None:
        self._repository = repository
        self._vector_search = vector_search
        self._lexical_search = lexical_search
        self._embedding_model = embedding_model
        self._reranker = reranker
        self._config = config
        self._embedding_dimension = embedding_dimension

    async def __call__(self, state: AppState) -> AppState:
        started_at = time.perf_counter()
        warnings = list(state.get("warnings", []))
        errors = list(state.get("errors", []))
        contexts = list(state.get("nvidia_contexts", []))
        metrics = dict(state.get("metrics", {}))
        counters = self._empty_counters()
        profiles = [
            profile for profile in state.get("validated_profiles", []) if is_usable_profile(profile)
        ]
        counters["input_profile_count"] = float(len(state.get("validated_profiles", [])))

        if not profiles:
            warnings.append("nvidia_rag_no_usable_profiles")
            return self._patch(started_at, contexts, warnings, errors, metrics, counters)

        try:
            documents = await self._repository.list_documents()
            chunks = await self._repository.list_chunks()
        except Exception:
            errors.append(self._error("nvidia_rag_retrieval_unavailable"))
            return self._patch(started_at, contexts, warnings, errors, metrics, counters)

        documents_by_id = {item.id: item for item in documents}
        chunks_by_id = {item.id: item for item in chunks}
        classifications = {
            item.startup_id: item for item in state.get("validated_classifications", [])
        }

        if not documents_by_id or not chunks_by_id:
            warnings.append("nvidia_rag_empty_knowledge_base")
            for profile in profiles:
                trace = self._query_traces(
                    profile,
                    classifications.get(profile.startup_id),
                    self._associated_gaps(profile, state.get("technical_gaps", [])),
                )[0]
                contexts.append(self._empty_context(profile, trace, "knowledge_base_empty"))
            counters["processed_startup_count"] = float(len(profiles))
            counters["insufficient_context_count"] = float(len(profiles))
            return self._patch(started_at, contexts, warnings, errors, metrics, counters)

        for profile in profiles:
            context, local_warnings, local_errors = await self._retrieve_startup(
                profile=profile,
                classification=classifications.get(profile.startup_id),
                gaps=self._associated_gaps(profile, state.get("technical_gaps", [])),
                documents_by_id=documents_by_id,
                chunks_by_id=chunks_by_id,
                counters=counters,
            )
            contexts.append(context)
            warnings.extend(local_warnings)
            errors.extend(local_errors)
            counters["processed_startup_count"] += 1
            if context.sufficiency.status is NvidiaContextStatus.SUFFICIENT:
                counters["sufficient_context_count"] += 1
            else:
                counters["insufficient_context_count"] += 1

        return self._patch(started_at, contexts, warnings, errors, metrics, counters)

    async def _retrieve_startup(
        self,
        *,
        profile: ValidatedStartupProfile,
        classification: ValidatedClassification | None,
        gaps: list[TechnicalGap],
        documents_by_id: dict[UUID, KnowledgeDocument],
        chunks_by_id: dict[UUID, KnowledgeChunk],
        counters: dict[str, float],
    ) -> tuple[NvidiaStartupContext, list[str], list[RecoverableError]]:
        warnings: list[str] = []
        errors: list[RecoverableError] = []
        traces = self._query_traces(profile, classification, gaps)
        merged: dict[UUID, NvidiaRetrievedChunk] = {}
        executed: list[NvidiaQueryTrace] = []

        for trace in traces:
            executed.append(trace)
            counters["attempt_count"] += 1
            multiplier = self._config.expansion_multiplier ** (trace.attempt - 1)
            vector_limit = min(100, max(1, round(self._config.vector_top_k * multiplier)))
            lexical_limit = min(100, max(1, round(self._config.lexical_top_k * multiplier)))
            vector_hits, vector_available = await self._vector_candidates(
                trace.text, vector_limit, warnings, counters
            )
            lexical_hits, lexical_available = self._lexical_candidates(
                trace.text, chunks_by_id, lexical_limit, warnings, counters
            )
            if not vector_available and not lexical_available:
                errors.append(self._error("nvidia_rag_retrieval_unavailable"))
                break

            ranked_vector = rank_search_hits(
                vector_hits,
                chunks_by_id=chunks_by_id,
                rrf_k=self._config.rrf_k,
            )
            ranked_lexical = rank_search_hits(
                lexical_hits,
                chunks_by_id=chunks_by_id,
                rrf_k=self._config.rrf_k,
                require_positive_score=True,
            )
            invalid_count = sum(
                hit.chunk_id not in chunks_by_id or not math.isfinite(hit.score)
                for hit in [*vector_hits, *lexical_hits]
            )
            if invalid_count:
                warnings.append("nvidia_rag_result_invalid")

            fused = fuse_ranked_hits(
                ranked_vector,
                ranked_lexical,
                vector_available=vector_available,
                lexical_available=lexical_available,
                vector_weight=self._config.vector_weight,
                lexical_weight=self._config.lexical_weight,
                chunks_by_id=chunks_by_id,
                limit=self._config.fused_top_k,
            )
            counters["deduplicated_candidate_count"] += float(len(fused))
            canonical = self._canonical_candidates(
                profile.startup_id,
                trace,
                fused,
                chunks_by_id,
                documents_by_id,
                warnings,
            )
            ranked, mode = await self._rerank(trace.text, canonical, warnings, counters)
            threshold = (
                self._config.min_reranker_score
                if mode is NvidiaRankingMode.RERANKER
                else self._config.min_hybrid_score
            )
            relevant = [item for item in ranked if self._effective_score(item) >= threshold]
            self._merge_results(merged, relevant)
            ordered = self._order_results(list(merged.values()))[: self._config.rerank_top_n]
            sufficiency = self._sufficiency(ordered)
            if sufficiency.status is NvidiaContextStatus.SUFFICIENT:
                counters["selected_chunk_count"] += float(len(ordered))
                return (
                    NvidiaStartupContext(
                        startup_id=profile.startup_id,
                        startup_name=profile.name,
                        attempted_queries=[item.text for item in executed],
                        query_traces=executed,
                        attempts=len(executed),
                        chunks=ordered,
                        sufficiency=sufficiency,
                    ),
                    warnings,
                    errors,
                )

        ordered = self._order_results(list(merged.values()))[: self._config.rerank_top_n]
        sufficiency = self._sufficiency(ordered)
        warnings.append(
            "nvidia_rag_irrelevant_results" if not ordered else "nvidia_rag_context_insufficient"
        )
        counters["selected_chunk_count"] += float(len(ordered))
        gap = NvidiaContextGap(
            code="nvidia_context_insufficient",
            message="The NVIDIA knowledge base did not provide enough relevant, citable context.",
        )
        return (
            NvidiaStartupContext(
                startup_id=profile.startup_id,
                startup_name=profile.name,
                attempted_queries=[item.text for item in executed],
                query_traces=executed,
                attempts=len(executed),
                chunks=ordered,
                sufficiency=sufficiency,
                gaps=[gap],
            ),
            warnings,
            errors,
        )

    async def _vector_candidates(
        self,
        query: str,
        limit: int,
        warnings: list[str],
        counters: dict[str, float],
    ) -> tuple[list[KnowledgeSearchHit], bool]:
        if self._embedding_model is None:
            warnings.append("nvidia_rag_vector_unavailable")
            counters["vector_fallback_count"] += 1
            return [], False
        try:
            counters["vector_query_count"] += 1
            vectors = await self._embedding_model.embed([query])
            if (
                len(vectors) != 1
                or len(vectors[0]) != self._embedding_dimension
                or any(not math.isfinite(value) for value in vectors[0])
            ):
                raise ValueError("invalid embedding")
            hits = await self._vector_search.search(vectors[0], limit=limit)
            counters["vector_candidate_count"] += float(len(hits))
            return hits, True
        except Exception:
            warnings.append("nvidia_rag_vector_unavailable")
            counters["vector_fallback_count"] += 1
            return [], False

    def _lexical_candidates(
        self,
        query: str,
        chunks: dict[UUID, KnowledgeChunk],
        limit: int,
        warnings: list[str],
        counters: dict[str, float],
    ) -> tuple[list[KnowledgeSearchHit], bool]:
        try:
            counters["lexical_query_count"] += 1
            hits = self._lexical_search.search(query, list(chunks.values()), limit=limit)
            counters["lexical_candidate_count"] += float(len(hits))
            return hits, True
        except Exception:
            warnings.append("nvidia_rag_lexical_unavailable")
            counters["lexical_fallback_count"] += 1
            return [], False

    def _canonical_candidates(
        self,
        startup_id: UUID,
        trace: NvidiaQueryTrace,
        fused: list[FusedHit],
        chunks: dict[UUID, KnowledgeChunk],
        documents: dict[UUID, KnowledgeDocument],
        warnings: list[str],
    ) -> list[NvidiaRetrievedChunk]:
        result: list[NvidiaRetrievedChunk] = []
        for item in fused:
            chunk = chunks.get(item.chunk_id)
            document = documents.get(chunk.document_id) if chunk else None
            try:
                if chunk is None or document is None:
                    raise ValueError("missing canonical record")
                source_key = document.source_key or ""
                technology = NvidiaTechnology(document.technology or "")
                metadata = chunk.metadata
                source_section = self._optional_string(metadata.get("source_section"))
                start_offset = self._optional_int(metadata.get("start_offset"))
                end_offset = self._optional_int(metadata.get("end_offset"))
                scores = NvidiaRetrievalScores(
                    vector_raw_score=item.vector.raw_score if item.vector else None,
                    vector_rank=item.vector.rank if item.vector else None,
                    vector_rank_score=item.vector.rank_score if item.vector else None,
                    bm25_raw_score=item.lexical.raw_score if item.lexical else None,
                    bm25_rank=item.lexical.rank if item.lexical else None,
                    bm25_rank_score=item.lexical.rank_score if item.lexical else None,
                    vector_weight=item.vector_weight,
                    lexical_weight=item.lexical_weight,
                    hybrid_score=item.hybrid_score,
                )
                result.append(
                    NvidiaRetrievedChunk(
                        startup_id=startup_id,
                        chunk_id=chunk.id,
                        document_id=document.id,
                        content=chunk.content,
                        title=document.title,
                        technology=technology,
                        source_key=source_key,
                        source_url=document.source_url,
                        chunk_index=chunk.chunk_index,
                        source_section=source_section,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        retrieval_attempts=[trace.attempt],
                        matched_queries=[trace.text],
                        scores=scores,
                    )
                )
            except (TypeError, ValueError):
                warnings.append("nvidia_rag_result_invalid")
        return result

    async def _rerank(
        self,
        query: str,
        candidates: list[NvidiaRetrievedChunk],
        warnings: list[str],
        counters: dict[str, float],
    ) -> tuple[list[NvidiaRetrievedChunk], NvidiaRankingMode]:
        fallback = self._order_results(candidates)[: self._config.rerank_top_n]
        if not candidates:
            return fallback, NvidiaRankingMode.HYBRID_FALLBACK
        if self._reranker is None:
            warnings.append("nvidia_rag_reranker_unavailable")
            counters["reranker_failure_count"] += 1
            counters["hybrid_fallback_count"] += 1
            return fallback, NvidiaRankingMode.HYBRID_FALLBACK
        try:
            counters["reranker_call_count"] += 1
            ranked = await self._reranker.rerank(
                query,
                [
                    RankedDocument(
                        document_id=str(item.chunk_id),
                        text=item.content,
                        score=item.scores.hybrid_score,
                    )
                    for item in candidates
                ],
                top_n=min(self._config.rerank_top_n, len(candidates)),
            )
            allowed = {str(item.chunk_id): item for item in candidates}
            if not ranked or len({item.document_id for item in ranked}) != len(ranked):
                raise ValueError("invalid reranker result")
            result = []
            for rank, item in enumerate(ranked, start=1):
                original = allowed.get(item.document_id)
                if (
                    original is None
                    or item.text != original.content
                    or not math.isfinite(item.score)
                    or not 0 <= item.score <= 1
                ):
                    raise ValueError("invalid reranker result")
                result.append(
                    original.model_copy(
                        update={
                            "scores": original.scores.model_copy(
                                update={"reranker_score": item.score, "reranker_rank": rank}
                            )
                        }
                    )
                )
            return self._order_results(result), NvidiaRankingMode.RERANKER
        except Exception:
            warnings.append("nvidia_rag_reranker_unavailable")
            counters["reranker_failure_count"] += 1
            counters["hybrid_fallback_count"] += 1
            return fallback, NvidiaRankingMode.HYBRID_FALLBACK

    def _sufficiency(self, chunks: list[NvidiaRetrievedChunk]) -> NvidiaContextSufficiency:
        mode = (
            NvidiaRankingMode.RERANKER
            if chunks and chunks[0].scores.reranker_score is not None
            else NvidiaRankingMode.HYBRID_FALLBACK
        )
        threshold = (
            self._config.min_reranker_score
            if mode is NvidiaRankingMode.RERANKER
            else self._config.min_hybrid_score
        )
        best_score = self._effective_score(chunks[0]) if chunks else None
        reasons = []
        if len(chunks) < self._config.min_relevant_chunks:
            reasons.append("minimum_relevant_chunks_not_met")
        document_count = len({item.document_id for item in chunks})
        if document_count < self._config.min_distinct_documents:
            reasons.append("minimum_distinct_documents_not_met")
        if best_score is None or best_score < threshold:
            reasons.append("minimum_relevance_score_not_met")
        return NvidiaContextSufficiency(
            status=(
                NvidiaContextStatus.INSUFFICIENT if reasons else NvidiaContextStatus.SUFFICIENT
            ),
            relevant_chunk_count=len(chunks),
            distinct_document_count=document_count,
            best_score=best_score,
            threshold=threshold,
            ranking_mode=mode,
            reasons=reasons,
        )

    def _query_traces(
        self,
        profile: ValidatedStartupProfile,
        classification: ValidatedClassification | None,
        gaps: list[TechnicalGap],
    ) -> list[NvidiaQueryTrace]:
        parts = self._query_parts(profile, classification, gaps)
        groups: list[tuple[str | None, list[QueryPart]]] = [(None, parts)]
        needs = [item for item in parts if item.field == ProfileField.TECHNICAL_NEEDS.value]
        technical_fields = {field.value for field in TECHNICAL_QUERY_FIELDS}
        technical = [item for item in parts if item.field in technical_fields]
        if needs:
            groups.append(("technical requirement", needs))
        if technical:
            groups.append(("technical context", technical))

        traces: list[NvidiaQueryTrace] = []
        seen: set[str] = set()
        for prefix, group in groups:
            text, selected = self._bounded_query(group)
            if prefix and text:
                text = f"{prefix}: {text}"[: self._config.max_query_chars].rstrip()
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            traces.append(
                NvidiaQueryTrace(
                    attempt=len(traces) + 1,
                    text=text,
                    fields=list(dict.fromkeys(item.field for item in selected)),
                    evidence_ids=list(
                        dict.fromkeys(
                            evidence_id for item in selected for evidence_id in item.evidence_ids
                        )
                    ),
                )
            )
            if len(traces) >= self._config.max_attempts:
                break
        return traces

    def _query_parts(
        self,
        profile: ValidatedStartupProfile,
        classification: ValidatedClassification | None,
        gaps: list[TechnicalGap],
    ) -> list[QueryPart]:
        parts: list[QueryPart] = []
        for field in QUERY_FIELD_ORDER:
            value = getattr(profile, field.value)
            facts = value if isinstance(value, list) else ([value] if value is not None else [])
            for fact in facts:
                parts.append(self._fact_part(field, fact))
        for gap in gaps:
            parts.insert(0, QueryPart("technical_gaps", gap.description, gap.evidence_ids))
        if classification is not None and classification.category is not None:
            parts.append(
                QueryPart(
                    "classification",
                    classification.category.value,
                    tuple(source.source_id for source in classification.evidence_references),
                )
            )
        unique: list[QueryPart] = []
        seen: set[str] = set()
        for item in parts:
            value = re.sub(r"\s+", " ", item.value).strip()
            if not value or value.casefold() in seen:
                continue
            seen.add(value.casefold())
            unique.append(replace(item, value=value))
        return unique

    def _bounded_query(self, parts: list[QueryPart]) -> tuple[str, list[QueryPart]]:
        selected: list[QueryPart] = []
        for item in parts[: self._config.max_query_items]:
            candidate = " | ".join([*(part.value for part in selected), item.value])
            if len(candidate) > self._config.max_query_chars:
                selected_length = len(" | ".join(part.value for part in selected))
                remaining = self._config.max_query_chars - selected_length
                if not selected and remaining > 0:
                    selected.append(replace(item, value=item.value[:remaining].rstrip()))
                break
            selected.append(item)
        return " | ".join(item.value for item in selected), selected

    @staticmethod
    def _fact_part(field: ProfileField, fact: ExtractedFact) -> QueryPart:
        return QueryPart(
            field.value,
            fact.value,
            tuple(source.source_id for source in fact.sources),
        )

    @staticmethod
    def _associated_gaps(
        profile: ValidatedStartupProfile, gaps: list[TechnicalGap]
    ) -> list[TechnicalGap]:
        source_ids = {
            source.source_id
            for field in QUERY_FIELD_ORDER
            for fact in (
                getattr(profile, field.value)
                if isinstance(getattr(profile, field.value), list)
                else [getattr(profile, field.value)]
            )
            if fact is not None
            for source in fact.sources
        }
        return [gap for gap in gaps if set(gap.evidence_ids) & source_ids]

    def _empty_context(
        self, profile: ValidatedStartupProfile, trace: NvidiaQueryTrace, reason: str
    ) -> NvidiaStartupContext:
        return NvidiaStartupContext(
            startup_id=profile.startup_id,
            startup_name=profile.name,
            attempted_queries=[trace.text],
            query_traces=[trace],
            attempts=1,
            sufficiency=NvidiaContextSufficiency(
                status=NvidiaContextStatus.INSUFFICIENT,
                relevant_chunk_count=0,
                distinct_document_count=0,
                threshold=self._config.min_hybrid_score,
                ranking_mode=NvidiaRankingMode.HYBRID_FALLBACK,
                reasons=[reason],
            ),
            gaps=[
                NvidiaContextGap(
                    code="nvidia_context_insufficient",
                    message="The NVIDIA knowledge base has no citable context for this startup.",
                )
            ],
        )

    @staticmethod
    def _merge_results(
        merged: dict[UUID, NvidiaRetrievedChunk], incoming: list[NvidiaRetrievedChunk]
    ) -> None:
        for item in incoming:
            current = merged.get(item.chunk_id)
            if current is None:
                merged[item.chunk_id] = item
                continue
            best = (
                item
                if NvidiaRagAgent._effective_score(item) > NvidiaRagAgent._effective_score(current)
                else current
            )
            merged[item.chunk_id] = best.model_copy(
                update={
                    "retrieval_attempts": sorted(
                        set(current.retrieval_attempts + item.retrieval_attempts)
                    ),
                    "matched_queries": list(
                        dict.fromkeys(current.matched_queries + item.matched_queries)
                    ),
                }
            )

    @staticmethod
    def _order_results(items: list[NvidiaRetrievedChunk]) -> list[NvidiaRetrievedChunk]:
        return sorted(
            items,
            key=lambda item: (
                -NvidiaRagAgent._effective_score(item),
                -item.scores.hybrid_score,
                item.document_id,
                item.chunk_index,
                item.chunk_id,
            ),
        )

    @staticmethod
    def _effective_score(item: NvidiaRetrievedChunk) -> float:
        return (
            item.scores.reranker_score
            if item.scores.reranker_score is not None
            else item.scores.hybrid_score
        )

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _error(code: str) -> RecoverableError:
        return RecoverableError(
            code=code,
            message="The NVIDIA knowledge retrieval service is unavailable.",
            node=NodeName.NVIDIA_RAG,
        )

    @staticmethod
    def _empty_counters() -> dict[str, float]:
        return {
            key: 0.0
            for key in (
                "input_profile_count",
                "processed_startup_count",
                "attempt_count",
                "vector_query_count",
                "lexical_query_count",
                "vector_candidate_count",
                "lexical_candidate_count",
                "deduplicated_candidate_count",
                "reranker_call_count",
                "reranker_failure_count",
                "selected_chunk_count",
                "sufficient_context_count",
                "insufficient_context_count",
                "vector_fallback_count",
                "lexical_fallback_count",
                "hybrid_fallback_count",
            )
        }

    @staticmethod
    def _patch(
        started_at: float,
        contexts: list[NvidiaStartupContext],
        warnings: list[str],
        errors: list[RecoverableError],
        metrics: dict[str, float],
        counters: dict[str, float],
    ) -> AppState:
        metrics.update(
            {
                "nvidia_rag_duration_ms": round((time.perf_counter() - started_at) * 1_000, 3),
                **{f"nvidia_rag_{key}": value for key, value in counters.items()},
            }
        )
        return AppState(
            nvidia_contexts=contexts,
            warnings=list(dict.fromkeys(warnings)),
            errors=errors,
            metrics=metrics,
        )
