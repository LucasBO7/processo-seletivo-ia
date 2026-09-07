from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from qdrant_client import models
from sqlalchemy import inspect

from app.application.contracts.retrieval import StartupSearchCriteria
from app.core.config import Settings
from app.domain.models import KnowledgeChunk, KnowledgeDocument, Startup, StartupDocument
from app.graph.agents.extractor import ExtractorAgent
from app.graph.agents.query_planner import create_query_planner_agent
from app.graph.agents.retriever import RetrieverAgent
from app.graph.builder import compile_analysis_workflow
from app.graph.model_policy import ModelRegistry
from app.graph.state import empty_state
from app.infrastructure.persistence.database import create_engine, create_session_factory
from app.infrastructure.persistence.repositories import (
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyKnowledgeDocumentRepository,
    SqlAlchemyStartupDocumentRepository,
    SqlAlchemyStartupRepository,
)
from app.infrastructure.vector.qdrant import create_qdrant_client, ensure_collection
from tests.fakes.providers import FakeChatModel, SequenceChatModel

pytestmark = pytest.mark.integration


def integration_settings() -> Settings:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Defina RUN_INTEGRATION_TESTS=1 para executar integrações reais.")
    return Settings()


async def test_schema_repositories_and_qdrant_are_consistent() -> None:
    settings = integration_settings()
    engine = create_engine(settings.postgres)
    sessions = create_session_factory(engine)
    qdrant = create_qdrant_client(settings.qdrant)
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
        assert {
            "startups",
            "startup_documents",
            "analysis_runs",
            "knowledge_documents",
            "knowledge_chunks",
        } <= tables

        startup_repository = SqlAlchemyStartupRepository(sessions)
        startup_document_repository = SqlAlchemyStartupDocumentRepository(sessions)
        knowledge_repository = SqlAlchemyKnowledgeDocumentRepository(sessions)
        chunk_repository = SqlAlchemyKnowledgeChunkRepository(sessions)

        suffix = uuid4().hex
        startup = Startup(
            name=f"Startup {suffix}",
            sector="Fintech / Crédito",
            stage="Seed",
            location="Brasil",
            team_size=25,
        )
        await startup_repository.add(startup)
        evidence = StartupDocument(
            startup_id=startup.id,
            document_type="site",
            title="Página oficial",
            content_text=f"Evidência pública da startup com sinal {suffix}.",
            source_url=f"https://example.com/{suffix}",
        )
        await startup_document_repository.add(evidence)
        financial_management = Startup(
            name=f"Financial SaaS {suffix}",
            sector="SaaS de Gestão Financeira",
            stage="Seed",
            location="Brasil",
            short_description=f"Gestão financeira com sinal {suffix}.",
            team_size=30,
        )
        await startup_repository.add(financial_management)
        financial_management_evidence = StartupDocument(
            startup_id=financial_management.id,
            document_type="site",
            title="Produto financeiro",
            content_text=f"SaaS financeiro com sinal {suffix}.",
            source_url=f"https://financial.example/{suffix}",
        )
        await startup_document_repository.add(financial_management_evidence)
        assert (await startup_repository.get(startup.id)) == startup
        assert (await startup_document_repository.list_for_startup(startup.id))[0] == evidence
        ranked = await startup_repository.search(
            StartupSearchCriteria(
                sectors=("fintech / crédito",),
                stages=("seed",),
                locations=("brasil",),
                text_terms=(suffix,),
            ),
            limit=5,
        )
        assert ranked[0].startup.id == startup.id
        assert ranked[0].score == 4.0
        assert (await startup_document_repository.list_for_startups([startup.id]))[0] == evidence

        model = FakeChatModel(
            json.dumps(
                {
                    "status": "ready",
                    "normalized_query": f"startup {suffix}",
                    "filters": {
                        "sectors": ["financial_services"],
                        "stages": ["seed"],
                        "locations": ["Brasil"],
                        "keywords": [suffix],
                    },
                    "analysis_strategy": {
                        "mode": "targeted",
                        "objectives": ["encontrar a startup de integração"],
                        "rationale": "Consulta com critérios suficientes.",
                    },
                    "ambiguities": [],
                    "clarification_questions": [],
                }
            )
        )
        workflow = compile_analysis_workflow(
            query_planner=create_query_planner_agent(
                registry=ModelRegistry(llm_fast=model, llm_heavy=model),
                config=settings.query_planner,
            ),
            retriever=RetrieverAgent(
                startups=startup_repository,
                documents=startup_document_repository,
                config=settings.retriever,
            ),
            extractor=ExtractorAgent(
                model=SequenceChatModel(
                    [
                        json.dumps(
                            {
                                "product": None,
                                "business_model": None,
                                "sector": None,
                                "target_audience": None,
                                "ai_use_cases": [],
                                "technologies": [],
                                "infrastructure": [],
                                "external_dependencies": [],
                                "technical_needs": [],
                                "claims": [
                                    {
                                        "value": document.content_text,
                                        "sources": [
                                            {
                                                "startup_id": str(document.startup_id),
                                                "source_id": str(document.id),
                                                "source_url": document.source_url,
                                            }
                                        ],
                                    }
                                ],
                                "unknown_fields": [
                                    "product",
                                    "business_model",
                                    "sector",
                                    "target_audience",
                                    "ai_use_cases",
                                    "technologies",
                                    "infrastructure",
                                    "external_dependencies",
                                    "technical_needs",
                                ],
                            }
                        )
                        for document in (financial_management_evidence, evidence)
                    ]
                ),
                config=settings.extractor,
            ),
        )
        workflow_result = await workflow.ainvoke(
            empty_state(
                run_id=uuid4(),
                correlation_id=f"integration-{suffix}",
                query=f"startup {suffix}",
            )
        )
        assert {item["startup_id"] for item in workflow_result["candidate_startups"]} == {
            startup.id,
            financial_management.id,
        }
        assert {source.source_id for source in workflow_result["selected_sources"]} == {
            evidence.id,
            financial_management_evidence.id,
        }
        assert {source.source_url for source in workflow_result["selected_sources"]} == {
            evidence.source_url,
            financial_management_evidence.source_url,
        }
        assert {profile.startup_id for profile in workflow_result["structured_profiles"]} == {
            startup.id,
            financial_management.id,
        }
        assert {
            claim.sources[0].source_id
            for profile in workflow_result["structured_profiles"]
            for claim in profile.claims
        } == {evidence.id, financial_management_evidence.id}

        async with engine.connect() as connection:
            startup_indexes = await connection.run_sync(
                lambda sync: {item["name"] for item in inspect(sync).get_indexes("startups")}
            )
        assert {
            "ix_startups_sector_lower",
            "ix_startups_stage_lower",
            "ix_startups_location_lower",
            "ix_startups_team_size",
        } <= startup_indexes

        knowledge = KnowledgeDocument(
            title="NVIDIA NIM",
            source_url=f"https://nvidia.com/{suffix}",
            content_type="documentation",
            content_hash=suffix.ljust(64, "0")[:64],
        )
        await knowledge_repository.add(knowledge)
        chunk = KnowledgeChunk(
            document_id=knowledge.id,
            content="NIM disponibiliza microsserviços de inferência.",
            chunk_index=0,
            content_hash=("a" + suffix).ljust(64, "0")[:64],
            metadata={"source_url": knowledge.source_url},
        )
        await chunk_repository.add(chunk)
        assert (await knowledge_repository.get(knowledge.id)) == knowledge
        assert (await chunk_repository.get(chunk.id)) == chunk

        await ensure_collection(qdrant, settings.qdrant)
        await ensure_collection(qdrant, settings.qdrant)
        await qdrant.upsert(
            collection_name=settings.qdrant.collection_name,
            points=[
                models.PointStruct(
                    id=str(chunk.id),
                    vector=[0.1] * settings.qdrant.embedding_dimension,
                    payload={"document_id": str(knowledge.id)},
                )
            ],
            wait=True,
        )
        points = await qdrant.retrieve(
            collection_name=settings.qdrant.collection_name,
            ids=[str(chunk.id)],
        )
        assert str(points[0].id) == str(chunk.id)
        assert str((await chunk_repository.list_for_document(knowledge.id))[0].id) == str(
            points[0].id
        )
    finally:
        await qdrant.close()
        await engine.dispose()
