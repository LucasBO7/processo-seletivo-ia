from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import ErrorResponse
from app.api.middleware import correlation_and_logging_middleware
from app.api.routes.query_plans import router as query_plans_router
from app.api.routes.search import router as search_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.resources import ApplicationResources
from app.graph.agents.briefing import create_briefing_agent
from app.graph.agents.evidence_validator import create_evidence_validator_agent
from app.graph.agents.extractor import create_extractor_agent
from app.graph.agents.nvidia_rag import NvidiaRagAgent
from app.graph.agents.query_planner import create_query_planner_agent
from app.graph.agents.recommendation import create_recommendation_agent
from app.graph.agents.retriever import RetrieverAgent
from app.graph.agents.startup_classifier import create_startup_classifier_agent
from app.graph.builder import compile_analysis_workflow
from app.graph.model_policy import ModelProfile, ModelRegistry
from app.infrastructure.persistence.database import (
    DatabaseReadinessProbe,
    create_engine,
    create_session_factory,
)
from app.infrastructure.persistence.knowledge import SqlAlchemyKnowledgeIngestionRepository
from app.infrastructure.persistence.repositories import (
    SqlAlchemyStartupDocumentRepository,
    SqlAlchemyStartupRepository,
)
from app.infrastructure.providers.cohere import CohereReranker
from app.infrastructure.providers.embeddings import OpenAICompatibleEmbeddingModel
from app.infrastructure.providers.groq import create_groq_chat_model
from app.infrastructure.retrieval.knowledge_bm25 import KnowledgeBM25Index
from app.infrastructure.vector.knowledge import QdrantKnowledgeVectorStore
from app.infrastructure.vector.qdrant import (
    QdrantReadinessProbe,
    create_qdrant_client,
    ensure_collection,
)

ResourceFactory = Callable[[Settings], Awaitable[ApplicationResources]]


def create_model_registry(settings: Settings) -> ModelRegistry:
    api_key = settings.groq.api_key.get_secret_value() if settings.groq.api_key else None
    llm_fast = create_groq_chat_model(
        config=settings.llm_fast,
        api_key=api_key,
        profile=ModelProfile.FAST,
    )
    llm_heavy = create_groq_chat_model(
        config=settings.llm_heavy,
        api_key=api_key,
        profile=ModelProfile.HEAVY,
    )
    return ModelRegistry(llm_fast=llm_fast, llm_heavy=llm_heavy)


async def create_resources(settings: Settings) -> ApplicationResources:
    model_registry = create_model_registry(settings)
    engine = create_engine(settings.postgres)
    sessions = create_session_factory(engine)
    query_planner = create_query_planner_agent(
        registry=model_registry,
        config=settings.query_planner,
    )
    retriever = RetrieverAgent(
        startups=SqlAlchemyStartupRepository(sessions),
        documents=SqlAlchemyStartupDocumentRepository(sessions),
        config=settings.retriever,
    )
    extractor = create_extractor_agent(registry=model_registry, config=settings.extractor)
    startup_classifier = create_startup_classifier_agent(
        registry=model_registry, config=settings.startup_classifier
    )
    evidence_validator = create_evidence_validator_agent(
        registry=model_registry, config=settings.evidence_validator
    )
    qdrant = create_qdrant_client(settings.qdrant)
    try:
        await ensure_collection(qdrant, settings.qdrant)
    except Exception:
        # The RAG node can continue with BM25 and reports Qdrant degradation safely.
        pass
    embedding_model = _create_embedding_model(settings)
    reranker = _create_reranker(settings)
    knowledge_repository = SqlAlchemyKnowledgeIngestionRepository(sessions)
    nvidia_rag = NvidiaRagAgent(
        repository=knowledge_repository,
        vector_search=QdrantKnowledgeVectorStore(qdrant, settings.qdrant.collection_name),
        lexical_search=KnowledgeBM25Index(),
        embedding_model=embedding_model,
        reranker=reranker,
        config=settings.nvidia_rag,
        embedding_dimension=settings.qdrant.embedding_dimension,
    )
    recommendation = create_recommendation_agent(
        registry=model_registry,
        config=settings.recommendation,
    )
    briefing = create_briefing_agent(registry=model_registry, config=settings.briefing)
    workflow = compile_analysis_workflow(
        query_planner=query_planner,
        retriever=retriever,
        extractor=extractor,
        startup_classifier=startup_classifier,
        evidence_validator=evidence_validator,
        nvidia_rag=nvidia_rag,
        recommendation=recommendation,
        briefing=briefing,
    )
    return ApplicationResources(
        engine=engine,
        sessions=sessions,
        qdrant=qdrant,
        postgres_probe=DatabaseReadinessProbe(engine),
        qdrant_probe=QdrantReadinessProbe(qdrant),
        llm_fast=model_registry.llm_fast,
        llm_heavy=model_registry.llm_heavy,
        model_registry=model_registry,
        query_planner=query_planner,
        extractor=extractor,
        startup_classifier=startup_classifier,
        evidence_validator=evidence_validator,
        embedding_model=embedding_model,
        reranker=reranker,
        nvidia_rag=nvidia_rag,
        recommendation=recommendation,
        briefing=briefing,
        workflow=workflow,
    )


def _create_embedding_model(settings: Settings) -> OpenAICompatibleEmbeddingModel | None:
    config = settings.embeddings
    if config.provider == "unset":
        return None
    if config.provider not in {"openai", "openai-compatible"}:
        raise ValueError("unsupported embedding provider")
    return OpenAICompatibleEmbeddingModel(config)


def _create_reranker(settings: Settings) -> CohereReranker | None:
    config = settings.reranker
    if config.api_key is None:
        return None
    if config.provider != "cohere":
        raise ValueError("unsupported reranker provider")
    return CohereReranker(
        api_key=config.api_key.get_secret_value(),
        model=config.model,
        timeout_seconds=config.timeout_seconds,
    )


def _error_response(request: Request, *, status_code: int, code: str, message: str) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    body = ErrorResponse(code=code, message=message, correlation_id=correlation_id)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def create_app(
    settings: Settings | None = None,
    resource_factory: ResourceFactory = create_resources,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.app.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resources = await resource_factory(resolved_settings)
        app.state.resources = resources
        try:
            yield
        finally:
            await resources.close()

    app = FastAPI(
        title=resolved_settings.app.name,
        version="0.1.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.middleware("http")(correlation_and_logging_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.http.cors_origins,
        allow_credentials=resolved_settings.http.cors_allow_credentials,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(
            request,
            status_code=exc.status_code,
            code=f"http_{exc.status_code}",
            message=str(exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del exc
        return _error_response(
            request,
            status_code=422,
            code="validation_error",
            message="A requisição contém dados inválidos.",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        del exc
        return _error_response(
            request,
            status_code=500,
            code="internal_error",
            message="Ocorreu um erro interno.",
        )

    app.include_router(query_plans_router)
    app.include_router(search_router)
    return app
