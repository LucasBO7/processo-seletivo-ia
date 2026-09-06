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
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.resources import ApplicationResources
from app.graph.model_policy import ModelProfile, ModelRegistry
from app.infrastructure.persistence.database import (
    DatabaseReadinessProbe,
    create_engine,
    create_session_factory,
)
from app.infrastructure.providers.groq import create_groq_chat_model
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
    qdrant = create_qdrant_client(settings.qdrant)
    try:
        await ensure_collection(qdrant, settings.qdrant)
    except Exception:
        await qdrant.close()
        await engine.dispose()
        raise
    return ApplicationResources(
        engine=engine,
        sessions=sessions,
        qdrant=qdrant,
        postgres_probe=DatabaseReadinessProbe(engine),
        qdrant_probe=QdrantReadinessProbe(qdrant),
        llm_fast=model_registry.llm_fast,
        llm_heavy=model_registry.llm_heavy,
        model_registry=model_registry,
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
    return app
