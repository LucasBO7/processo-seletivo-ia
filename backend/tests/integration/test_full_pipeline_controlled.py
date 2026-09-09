from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from app.application.contracts.knowledge_ingestion import NvidiaTechnology
from app.application.contracts.retrieval import RankedStartup, StartupSearchCriteria
from app.application.ports.knowledge import KnowledgeSearchHit
from app.core.config import Settings
from app.domain.models import KnowledgeChunk, KnowledgeDocument, Startup, StartupDocument
from app.graph.agents.briefing import create_briefing_agent
from app.graph.agents.evidence_validator import create_evidence_validator_agent
from app.graph.agents.extractor import create_extractor_agent
from app.graph.agents.nvidia_rag import NvidiaRagAgent
from app.graph.agents.query_planner import create_query_planner_agent
from app.graph.agents.recommendation import create_recommendation_agent
from app.graph.agents.retriever import RetrieverAgent
from app.graph.agents.startup_classifier import create_startup_classifier_agent
from app.graph.builder import compile_analysis_workflow
from app.graph.model_policy import ModelRegistry
from app.graph.state import empty_state
from tests.fakes.providers import FakeEmbeddingModel, FakeReranker, SequenceChatModel

pytestmark = pytest.mark.integration


class ControlledStartupRepository:
    def __init__(self, startup: Startup) -> None:
        self.startup = startup
        self.calls = 0

    async def search(self, criteria: StartupSearchCriteria, *, limit: int) -> list[RankedStartup]:
        del criteria, limit
        self.calls += 1
        return [RankedStartup(startup=self.startup, score=1.0)]

    async def add(self, startup: Startup) -> Startup:
        self.startup = startup
        return startup

    async def get(self, startup_id: UUID) -> Startup | None:
        return self.startup if self.startup.id == startup_id else None


class ControlledStartupDocumentRepository:
    def __init__(self, document: StartupDocument) -> None:
        self.document = document
        self.calls = 0

    async def list_for_startups(self, startup_ids: list[UUID]) -> list[StartupDocument]:
        self.calls += 1
        return [self.document] if self.document.startup_id in startup_ids else []

    async def add(self, document: StartupDocument) -> StartupDocument:
        self.document = document
        return document

    async def list_for_startup(self, startup_id: UUID) -> list[StartupDocument]:
        return [self.document] if self.document.startup_id == startup_id else []


class ControlledKnowledgeRepository:
    def __init__(self, documents: list[KnowledgeDocument], chunks: list[KnowledgeChunk]) -> None:
        self.documents = documents
        self.chunks = chunks
        self.calls = 0

    async def list_documents(self) -> list[KnowledgeDocument]:
        self.calls += 1
        return self.documents

    async def list_chunks(self) -> list[KnowledgeChunk]:
        return self.chunks


class ControlledVectorSearch:
    def __init__(self, hits: list[KnowledgeSearchHit]) -> None:
        self.hits = hits
        self.calls = 0

    async def search(self, vector: Sequence[float], *, limit: int) -> list[KnowledgeSearchHit]:
        del vector
        self.calls += 1
        return self.hits[:limit]


class ControlledLexicalSearch:
    def __init__(self, hits: list[KnowledgeSearchHit]) -> None:
        self.hits = hits
        self.calls = 0

    def search(
        self, query: str, chunks: Sequence[KnowledgeChunk], *, limit: int
    ) -> list[KnowledgeSearchHit]:
        del query, chunks
        self.calls += 1
        return self.hits[:limit]


def compact(payload: object) -> str:
    return json.dumps(payload, separators=(",", ":"))


def source_pointer(startup_id: UUID, source_id: UUID, source_url: str) -> dict[str, str]:
    return {
        "startup_id": str(startup_id),
        "source_id": str(source_id),
        "source_url": source_url,
    }


def supported_assessment(
    key: str, startup_id: UUID, source_id: UUID, source_url: str
) -> dict[str, object]:
    return {
        "claim_key": key,
        "status": "supported",
        "justification": "The startup document directly supports this item.",
        "analyzed_sources": [
            {
                "startup_id": str(startup_id),
                "source_id": str(source_id),
                "source_url": source_url,
                "verdict": "supports",
            }
        ],
    }


@pytest.mark.asyncio
async def test_full_pipeline_runs_all_real_agents_with_controlled_infrastructure() -> None:
    startup = Startup(name="Vision Health", sector="Healthcare", stage="Seed")
    startup_document = StartupDocument(
        startup_id=startup.id,
        document_type="site",
        title="Product",
        content_text=(
            "Vision Health provides a core medical inference product using Python and needs "
            "lower inference latency."
        ),
        source_url="https://startup.example/product",
    )
    pointer = source_pointer(startup.id, startup_document.id, startup_document.source_url)

    nim_document = KnowledgeDocument(
        id=uuid4(),
        source_key="nim",
        title="NVIDIA NIM",
        source_url="https://www.nvidia.com/nim/",
        technology=NvidiaTechnology.NVIDIA_NIM.value,
        content_type="html",
        content_hash="a" * 64,
    )
    inception_document = KnowledgeDocument(
        id=uuid4(),
        source_key="inception",
        title="NVIDIA Inception",
        source_url="https://www.nvidia.com/startups/",
        technology=NvidiaTechnology.NVIDIA_INCEPTION.value,
        content_type="html",
        content_hash="b" * 64,
    )
    nim_chunk = KnowledgeChunk(
        id=uuid4(),
        document_id=nim_document.id,
        content="NVIDIA NIM provides inference API microservices.",
        chunk_index=0,
        content_hash="c" * 64,
        metadata={"source_section": "API", "start_offset": 0, "end_offset": 48},
    )
    inception_chunk = KnowledgeChunk(
        id=uuid4(),
        document_id=inception_document.id,
        content="NVIDIA Inception supports startups with program resources.",
        chunk_index=0,
        content_hash="d" * 64,
        metadata={"source_section": "Program", "start_offset": 0, "end_offset": 58},
    )
    hits = [
        KnowledgeSearchHit(chunk_id=nim_chunk.id, score=0.9),
        KnowledgeSearchHit(chunk_id=inception_chunk.id, score=0.8),
    ]

    fast_model = SequenceChatModel(
        [
            compact(
                {
                    "status": "ready",
                    "normalized_query": "healthcare inference startups",
                    "filters": {},
                    "analysis_strategy": {
                        "mode": "exploratory",
                        "objectives": ["identify startups"],
                        "rationale": "The query is executable.",
                    },
                    "ambiguities": [],
                    "clarification_questions": [],
                }
            ),
            compact(
                {
                    "product": {
                        "value": "Core medical inference product",
                        "sources": [pointer],
                    },
                    "business_model": None,
                    "sector": None,
                    "target_audience": None,
                    "ai_use_cases": [],
                    "technologies": [{"value": "Python inference API", "sources": [pointer]}],
                    "infrastructure": [],
                    "external_dependencies": [],
                    "technical_needs": [
                        {
                            "value": "Required inference latency improvement",
                            "sources": [pointer],
                        }
                    ],
                    "claims": [],
                    "unknown_fields": [
                        "business_model",
                        "sector",
                        "target_audience",
                        "ai_use_cases",
                        "infrastructure",
                        "external_dependencies",
                        "claims",
                    ],
                }
            ),
            compact(
                {
                    "assessments": [
                        supported_assessment(
                            key, startup.id, startup_document.id, startup_document.source_url
                        )
                        for key in (
                            "product",
                            "technologies[0]",
                            "technical_needs[0]",
                            "classification",
                        )
                    ]
                }
            ),
        ]
    )
    heavy_model = SequenceChatModel(
        [
            compact(
                {
                    "status": "classified",
                    "category": "ai-native",
                    "justification": "The core product depends on medical inference.",
                    "confidence": "high",
                    "signals": [
                        {
                            "type": "core_ai_dependency",
                            "description": "Core product depends on medical inference",
                            "sources": [pointer],
                        }
                    ],
                }
            ),
            compact(
                {
                    "candidates": [
                        {
                            "technology": "nvidia_nim",
                            "need_keys": ["need:1"],
                            "technical_justification": (
                                "The NVIDIA NIM inference API addresses the latency need."
                            ),
                            "business_justification": (
                                "Inference supports the startup core medical product."
                            ),
                            "next_action": "NVIDIA team should run an inference discovery.",
                            "startup_evidence_ids": [str(startup_document.id)],
                            "nvidia_chunk_ids": [str(nim_chunk.id)],
                            "need_criticality": "blocker",
                            "business_relevance": "core",
                            "priority": "high",
                            "priority_evidence_ids": [str(startup_document.id)],
                            "integration_scope": "configuration_or_api",
                            "infrastructure_change": "none",
                            "specialized_skills": "standard",
                            "implementation_complexity": "low",
                            "complexity_nvidia_chunk_ids": [str(nim_chunk.id)],
                        }
                    ]
                }
            ),
            compact(
                {
                    "executive_summary": [
                        {
                            "kind": "supported_inference",
                            "text": "The inference product can use NVIDIA NIM.",
                            "citation_ids": ["S1", "N1"],
                        }
                    ],
                    "inception_opportunities": [
                        {
                            "kind": "supported_inference",
                            "text": "The startup product may explore NVIDIA Inception.",
                            "citation_ids": ["S1", "N2"],
                        }
                    ],
                    "uncertainties_and_gaps": [
                        {
                            "kind": "gap",
                            "text": "Inference latency remains to be validated.",
                            "citation_ids": ["S1"],
                        }
                    ],
                }
            ),
        ]
    )
    registry = ModelRegistry(llm_fast=fast_model, llm_heavy=heavy_model)
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
        qdrant={"url": "http://localhost:6333", "embedding_dimension": 3},
        nvidia_rag={
            "min_relevant_chunks": 2,
            "min_distinct_documents": 2,
            "min_reranker_score": 0.1,
        },
    )
    startup_repository = ControlledStartupRepository(startup)
    startup_documents = ControlledStartupDocumentRepository(startup_document)
    knowledge = ControlledKnowledgeRepository(
        [nim_document, inception_document], [nim_chunk, inception_chunk]
    )
    vector = ControlledVectorSearch(hits)
    lexical = ControlledLexicalSearch(hits)
    workflow = compile_analysis_workflow(
        query_planner=create_query_planner_agent(registry=registry, config=settings.query_planner),
        retriever=RetrieverAgent(
            startups=startup_repository,
            documents=startup_documents,
            config=settings.retriever,
        ),
        extractor=create_extractor_agent(registry=registry, config=settings.extractor),
        startup_classifier=create_startup_classifier_agent(
            registry=registry, config=settings.startup_classifier
        ),
        evidence_validator=create_evidence_validator_agent(
            registry=registry, config=settings.evidence_validator
        ),
        nvidia_rag=NvidiaRagAgent(
            repository=knowledge,
            vector_search=vector,
            lexical_search=lexical,
            embedding_model=FakeEmbeddingModel(3),
            reranker=FakeReranker(),
            config=settings.nvidia_rag,
            embedding_dimension=3,
        ),
        recommendation=create_recommendation_agent(
            registry=registry, config=settings.recommendation
        ),
        briefing=create_briefing_agent(registry=registry, config=settings.briefing),
    )
    run_id = uuid4()

    result = await workflow.ainvoke(
        empty_state(
            run_id=run_id,
            correlation_id="controlled-full-pipeline",
            query="healthcare inference startups",
        )
    )

    assert result["run_id"] == run_id
    assert result["correlation_id"] == "controlled-full-pipeline"
    assert result["candidate_startups"][0]["startup_id"] == startup.id
    assert result["selected_sources"][0].source_id == startup_document.id
    assert result["selected_sources"][0].source_url == startup_document.source_url
    assert result["validated_profiles"][0].startup_id == startup.id
    assert result["nvidia_contexts"][0].chunks[0].chunk_id == nim_chunk.id
    assert result["nvidia_contexts"][0].chunks[0].source_url == nim_document.source_url
    assert result["recommendations"], (result["warnings"], result["errors"])
    assert result["recommendations"][0].startup_evidence[0].source_id == startup_document.id
    assert result["recommendations"][0].nvidia_evidence[0].chunk_id == nim_chunk.id
    assert result["briefings"][0].startup_citations[0].source_id == startup_document.id
    assert {item.source_url for item in result["briefings"][0].nvidia_citations} == {
        nim_document.source_url,
        inception_document.source_url,
    }
    assert not result["errors"]
    for prefix in (
        "query_planner",
        "retriever",
        "extractor",
        "classifier",
        "evidence_validator",
        "nvidia_rag",
        "recommendation",
        "briefing",
    ):
        assert any(key.startswith(f"{prefix}_") for key in result["metrics"])
    assert len(fast_model.calls) == 3
    assert len(heavy_model.calls) == 3
    assert startup_repository.calls == 1
    assert startup_documents.calls == 1
    assert knowledge.calls == 1
    assert vector.calls >= 1
    assert lexical.calls >= 1
