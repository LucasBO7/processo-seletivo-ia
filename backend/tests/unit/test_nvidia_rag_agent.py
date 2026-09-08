from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import pytest

from app.application.contracts.evidence_validation import ValidatedStartupProfile
from app.application.contracts.extraction import ExtractedFact, ExtractionSource, ProfileField
from app.application.contracts.knowledge_ingestion import NvidiaTechnology
from app.application.contracts.nvidia_rag import NvidiaContextStatus, NvidiaRankingMode
from app.application.ports.knowledge import KnowledgeSearchHit
from app.application.ports.providers import RankedDocument, Reranker
from app.core.config import NvidiaRagConfig
from app.domain.models import KnowledgeChunk, KnowledgeDocument
from app.graph.agents.nvidia_rag import (
    NvidiaRagAgent,
    fuse_ranked_hits,
    normalized_rank_score,
    rank_search_hits,
)
from app.graph.state import AppState
from tests.fakes.providers import FakeEmbeddingModel, FakeReranker


class FakeKnowledgeRepository:
    def __init__(
        self,
        documents: list[KnowledgeDocument],
        chunks: list[KnowledgeChunk],
        *,
        error: Exception | None = None,
    ) -> None:
        self.documents = documents
        self.chunks = chunks
        self.error = error
        self.calls = 0

    async def list_documents(self) -> list[KnowledgeDocument]:
        self.calls += 1
        if self.error:
            raise self.error
        return self.documents

    async def list_chunks(self) -> list[KnowledgeChunk]:
        if self.error:
            raise self.error
        return self.chunks


class FakeVectorSearch:
    def __init__(self, hits: list[KnowledgeSearchHit], *, error: Exception | None = None) -> None:
        self.hits = hits
        self.error = error
        self.calls: list[int] = []

    async def search(self, vector: Sequence[float], *, limit: int) -> list[KnowledgeSearchHit]:
        del vector
        self.calls.append(limit)
        if self.error:
            raise self.error
        return self.hits[:limit]


class FakeLexicalSearch:
    def __init__(self, hits: list[KnowledgeSearchHit], *, error: Exception | None = None) -> None:
        self.hits = hits
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def search(
        self, query: str, chunks: Sequence[KnowledgeChunk], *, limit: int
    ) -> list[KnowledgeSearchHit]:
        del chunks
        self.calls.append((query, limit))
        if self.error:
            raise self.error
        return self.hits[:limit]


class FailingReranker:
    async def rerank(
        self,
        query: str,
        documents: Sequence[RankedDocument],
        *,
        top_n: int,
    ) -> list[RankedDocument]:
        del query, documents, top_n
        raise RuntimeError("secret provider response")


class LowScoreReranker:
    async def rerank(
        self,
        query: str,
        documents: Sequence[RankedDocument],
        *,
        top_n: int,
    ) -> list[RankedDocument]:
        del query
        return [RankedDocument(item.document_id, item.text, 0.01) for item in documents[:top_n]]


class InvalidReranker:
    async def rerank(
        self,
        query: str,
        documents: Sequence[RankedDocument],
        *,
        top_n: int,
    ) -> list[RankedDocument]:
        del query, documents, top_n
        return [RankedDocument(str(uuid4()), "foreign text", 0.9)]


def startup_profile() -> ValidatedStartupProfile:
    startup_id = uuid4()
    source = ExtractionSource(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://startup.example/evidence",
    )
    return ValidatedStartupProfile(
        startup_id=startup_id,
        name="Vision Health",
        product=ExtractedFact(value="Medical image analysis", sources=[source]),
        sector=ExtractedFact(value="Healthcare", sources=[source]),
        ai_use_cases=[ExtractedFact(value="Computer vision diagnostics", sources=[source])],
        technologies=[ExtractedFact(value="Python inference service", sources=[source])],
        technical_needs=[ExtractedFact(value="Low latency model serving", sources=[source])],
        unknown_fields=[
            ProfileField.BUSINESS_MODEL,
            ProfileField.TARGET_AUDIENCE,
            ProfileField.INFRASTRUCTURE,
            ProfileField.EXTERNAL_DEPENDENCIES,
            ProfileField.CLAIMS,
        ],
    )


def knowledge_corpus() -> tuple[list[KnowledgeDocument], list[KnowledgeChunk]]:
    first_document = KnowledgeDocument(
        id=uuid4(),
        source_key="triton-docs",
        title="Triton Inference Server",
        source_url="https://docs.nvidia.com/deeplearning/triton/",
        technology=NvidiaTechnology.TRITON_INFERENCE_SERVER.value,
        content_type="html",
        content_hash="a" * 64,
    )
    second_document = KnowledgeDocument(
        id=uuid4(),
        source_key="tensorrt-llm",
        title="TensorRT-LLM",
        source_url="https://github.com/NVIDIA/TensorRT-LLM",
        technology=NvidiaTechnology.TENSORRT_LLM.value,
        content_type="markdown",
        content_hash="b" * 64,
    )
    chunks = [
        KnowledgeChunk(
            id=uuid4(),
            document_id=first_document.id,
            content="Triton serves inference workloads with dynamic batching.",
            chunk_index=0,
            content_hash="c" * 64,
            metadata={
                "source_url": "https://stale.invalid/payload",
                "source_section": "Dynamic batching",
                "start_offset": 0,
                "end_offset": 55,
            },
        ),
        KnowledgeChunk(
            id=uuid4(),
            document_id=second_document.id,
            content="TensorRT-LLM optimizes large language model inference.",
            chunk_index=0,
            content_hash="d" * 64,
            metadata={"source_section": "Overview", "start_offset": 0, "end_offset": 53},
        ),
    ]
    return [first_document, second_document], chunks


def build_agent(
    repository: FakeKnowledgeRepository,
    vector: FakeVectorSearch,
    lexical: FakeLexicalSearch,
    *,
    reranker: Reranker | None = None,
    embedding: FakeEmbeddingModel | None = None,
    config: NvidiaRagConfig | None = None,
) -> NvidiaRagAgent:
    return NvidiaRagAgent(
        repository=repository,
        vector_search=vector,
        lexical_search=lexical,
        embedding_model=embedding,
        reranker=reranker,
        config=config
        or NvidiaRagConfig(
            min_relevant_chunks=2,
            min_distinct_documents=2,
            min_reranker_score=0.1,
        ),
        embedding_dimension=3,
    )


def test_weighted_rrf_is_normalized_deduplicated_and_stable() -> None:
    _, chunks = knowledge_corpus()
    by_id = {item.id: item for item in chunks}
    duplicate = KnowledgeSearchHit(chunk_id=chunks[0].id, score=0.1)
    vector = rank_search_hits(
        [KnowledgeSearchHit(chunks[0].id, 0.9), duplicate],
        chunks_by_id=by_id,
        rrf_k=60,
    )
    lexical = rank_search_hits(
        [KnowledgeSearchHit(chunks[1].id, 5.0), KnowledgeSearchHit(chunks[0].id, 4.0)],
        chunks_by_id=by_id,
        rrf_k=60,
        require_positive_score=True,
    )

    fused = fuse_ranked_hits(
        vector,
        lexical,
        vector_available=True,
        lexical_available=True,
        vector_weight=0.5,
        lexical_weight=0.5,
        chunks_by_id=by_id,
        limit=10,
    )

    assert normalized_rank_score(1, 60) == 1
    assert len(fused) == 2
    assert fused[0].chunk_id == chunks[0].id
    assert fused[0].hybrid_score == pytest.approx(0.5 + 0.5 * normalized_rank_score(2, 60))


@pytest.mark.asyncio
async def test_agent_returns_reranked_citable_context_from_postgres() -> None:
    documents, chunks = knowledge_corpus()
    hits = [
        KnowledgeSearchHit(chunks[0].id, 0.9),
        KnowledgeSearchHit(chunks[1].id, 0.8),
    ]
    profile = startup_profile()
    agent = build_agent(
        FakeKnowledgeRepository(documents, chunks),
        FakeVectorSearch(hits),
        FakeLexicalSearch(list(reversed(hits))),
        embedding=FakeEmbeddingModel(3),
        reranker=FakeReranker(),
    )

    result = await agent(AppState(validated_profiles=[profile], warnings=[], errors=[], metrics={}))

    context = result["nvidia_contexts"][0]
    assert context.sufficiency.status is NvidiaContextStatus.SUFFICIENT
    assert context.sufficiency.ranking_mode is NvidiaRankingMode.RERANKER
    assert len(context.chunks) == 2
    assert context.chunks[0].source_url in {item.source_url for item in documents}
    assert context.chunks[0].source_url != "https://stale.invalid/payload"
    assert context.chunks[0].scores.vector_raw_score is not None
    assert context.chunks[0].scores.bm25_raw_score is not None
    assert context.chunks[0].scores.reranker_score is not None
    assert context.query_traces[0].evidence_ids
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_agent_degrades_to_bm25_and_hybrid_order() -> None:
    documents, chunks = knowledge_corpus()
    lexical_hits = [
        KnowledgeSearchHit(chunks[0].id, 2.0),
        KnowledgeSearchHit(chunks[1].id, 1.0),
    ]
    profile = startup_profile()
    agent = build_agent(
        FakeKnowledgeRepository(documents, chunks),
        FakeVectorSearch([], error=RuntimeError("qdrant secret")),
        FakeLexicalSearch(lexical_hits),
        embedding=FakeEmbeddingModel(3),
        reranker=FailingReranker(),
        config=NvidiaRagConfig(
            min_relevant_chunks=2,
            min_distinct_documents=2,
            min_hybrid_score=0.5,
        ),
    )

    result = await agent(AppState(validated_profiles=[profile]))

    context = result["nvidia_contexts"][0]
    assert context.sufficiency.status is NvidiaContextStatus.SUFFICIENT
    assert context.sufficiency.ranking_mode is NvidiaRankingMode.HYBRID_FALLBACK
    assert context.chunks[0].scores.vector_weight == 0
    assert context.chunks[0].scores.lexical_weight == 1
    assert "nvidia_rag_vector_unavailable" in result["warnings"]
    assert "nvidia_rag_reranker_unavailable" in result["warnings"]
    assert "secret" not in str(result)


@pytest.mark.asyncio
async def test_invalid_provider_results_are_safely_ignored_or_fallback() -> None:
    documents, chunks = knowledge_corpus()
    unknown_id = uuid4()
    vector_hits = [
        KnowledgeSearchHit(unknown_id, 1.0),
        KnowledgeSearchHit(chunks[0].id, float("nan")),
        KnowledgeSearchHit(chunks[0].id, 0.8),
    ]
    lexical_hits = [KnowledgeSearchHit(chunks[0].id, 2.0)]
    agent = build_agent(
        FakeKnowledgeRepository(documents, chunks),
        FakeVectorSearch(vector_hits),
        FakeLexicalSearch(lexical_hits),
        embedding=FakeEmbeddingModel(3),
        reranker=InvalidReranker(),
        config=NvidiaRagConfig(
            min_relevant_chunks=1,
            min_distinct_documents=1,
            min_hybrid_score=0.1,
        ),
    )

    result = await agent(AppState(validated_profiles=[startup_profile()]))

    context = result["nvidia_contexts"][0]
    assert context.sufficiency.status is NvidiaContextStatus.SUFFICIENT
    assert context.chunks[0].chunk_id == chunks[0].id
    assert context.chunks[0].scores.reranker_score is None
    assert "nvidia_rag_result_invalid" in result["warnings"]
    assert "nvidia_rag_reranker_unavailable" in result["warnings"]


@pytest.mark.asyncio
async def test_postgres_failure_is_sanitized() -> None:
    repository = FakeKnowledgeRepository([], [], error=RuntimeError("database-password"))
    agent = build_agent(repository, FakeVectorSearch([]), FakeLexicalSearch([]))

    result = await agent(AppState(validated_profiles=[startup_profile()]))

    assert result["errors"][0].code == "nvidia_rag_retrieval_unavailable"
    assert result["nvidia_contexts"] == []
    assert "database-password" not in str(result)


@pytest.mark.asyncio
async def test_empty_base_returns_explicit_gap_without_providers() -> None:
    profile = startup_profile()
    repository = FakeKnowledgeRepository([], [])
    vector = FakeVectorSearch([])
    lexical = FakeLexicalSearch([])
    agent = build_agent(repository, vector, lexical)

    result = await agent(AppState(validated_profiles=[profile]))

    context = result["nvidia_contexts"][0]
    assert context.sufficiency.status is NvidiaContextStatus.INSUFFICIENT
    assert context.gaps[0].code == "nvidia_context_insufficient"
    assert result["warnings"] == ["nvidia_rag_empty_knowledge_base"]
    assert vector.calls == []
    assert lexical.calls == []


@pytest.mark.asyncio
async def test_both_channels_unavailable_returns_sanitized_recoverable_error() -> None:
    documents, chunks = knowledge_corpus()
    profile = startup_profile()
    agent = build_agent(
        FakeKnowledgeRepository(documents, chunks),
        FakeVectorSearch([], error=RuntimeError("qdrant-key")),
        FakeLexicalSearch([], error=RuntimeError("index-path")),
        embedding=FakeEmbeddingModel(3),
    )

    result = await agent(AppState(validated_profiles=[profile]))

    assert result["errors"][0].code == "nvidia_rag_retrieval_unavailable"
    assert "qdrant-key" not in str(result)
    assert "index-path" not in str(result)
    assert result["nvidia_contexts"][0].sufficiency.status is NvidiaContextStatus.INSUFFICIENT


@pytest.mark.asyncio
async def test_insufficient_context_reformulates_up_to_configured_limit() -> None:
    documents, chunks = knowledge_corpus()
    hits = [KnowledgeSearchHit(chunks[0].id, 0.9)]
    profile = startup_profile()
    lexical = FakeLexicalSearch(hits)
    vector = FakeVectorSearch(hits)
    agent = build_agent(
        FakeKnowledgeRepository(documents, chunks),
        vector,
        lexical,
        embedding=FakeEmbeddingModel(3),
        reranker=LowScoreReranker(),
        config=NvidiaRagConfig(
            min_relevant_chunks=1,
            min_distinct_documents=1,
            min_reranker_score=0.9,
            max_attempts=3,
        ),
    )

    result = await agent(AppState(validated_profiles=[profile]))

    context = result["nvidia_contexts"][0]
    assert context.sufficiency.status is NvidiaContextStatus.INSUFFICIENT
    assert context.attempts == 3
    assert len(set(context.attempted_queries)) == 3
    assert vector.calls == [20, 40, 80]
    assert [limit for _, limit in lexical.calls] == [20, 40, 80]
    assert context.gaps
    assert "nvidia_rag_irrelevant_results" in result["warnings"]


@pytest.mark.asyncio
async def test_no_usable_profile_performs_no_repository_io() -> None:
    repository = FakeKnowledgeRepository([], [])
    empty_profile = ValidatedStartupProfile(
        startup_id=uuid4(), name="Empty", unknown_fields=list(ProfileField)
    )
    agent = build_agent(repository, FakeVectorSearch([]), FakeLexicalSearch([]))

    result = await agent(AppState(validated_profiles=[empty_profile]))

    assert repository.calls == 0
    assert result["nvidia_contexts"] == []
    assert result["warnings"] == ["nvidia_rag_no_usable_profiles"]
