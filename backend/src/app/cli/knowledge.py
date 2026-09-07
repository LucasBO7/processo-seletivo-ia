from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.application.ports.knowledge import (
    KnowledgeIngestionRepository,
    KnowledgeSourceClient,
    KnowledgeVectorStore,
)
from app.application.ports.providers import EmbeddingModel
from app.application.services.knowledge_ingestion import NvidiaKnowledgeIngestionService
from app.application.services.knowledge_verification import verify_knowledge_base
from app.core.config import Settings
from app.infrastructure.ingestion.dry_run import (
    DryRunKnowledgeRepository,
    DryRunKnowledgeVectorStore,
)
from app.infrastructure.ingestion.http_source import (
    FileKnowledgeSourceClient,
    HttpKnowledgeSourceClient,
)
from app.infrastructure.ingestion.manifest import load_manifest
from app.infrastructure.ingestion.preparer import DeterministicKnowledgePreparer
from app.infrastructure.persistence.database import create_engine, create_session_factory
from app.infrastructure.persistence.knowledge import SqlAlchemyKnowledgeIngestionRepository
from app.infrastructure.providers.embeddings import (
    DeterministicEmbeddingModel,
    OpenAICompatibleEmbeddingModel,
)
from app.infrastructure.retrieval.knowledge_bm25 import KnowledgeBM25Index
from app.infrastructure.vector.knowledge import QdrantKnowledgeVectorStore
from app.infrastructure.vector.qdrant import create_qdrant_client, ensure_collection


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="startup-radar-knowledge")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("ingest", "dry-run"):
        command = subcommands.add_parser(name)
        command.add_argument("--manifest", type=Path)
        command.add_argument("--technology")
        command.add_argument("--source-key")
        command.add_argument("--fixture-dir", type=Path)
        command.add_argument("--offline-embeddings", action="store_true")
    verify = subcommands.add_parser("verify")
    verify.add_argument("--manifest", type=Path)
    return parser


def run() -> None:
    arguments = _parser().parse_args()
    raise SystemExit(asyncio.run(_execute(arguments)))


async def _execute(arguments: argparse.Namespace, *, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    manifest = load_manifest(arguments.manifest or settings.knowledge_ingestion.manifest_path)
    if arguments.command == "dry-run":
        source_client = _create_source_client(arguments, settings, manifest.allowed_domains)
        embedding_model = _create_embedding_model(arguments, settings)
        try:
            report = await _create_service(
                settings,
                source_client,
                DryRunKnowledgeRepository(),
                DryRunKnowledgeVectorStore(),
                embedding_model,
            ).ingest(
                manifest,
                dry_run=True,
                technology=arguments.technology,
                source_key=arguments.source_key,
            )
            _print_report(report.model_dump(mode="json"))
            return 1 if any(item.outcome.value == "failed" for item in report.results) else 0
        finally:
            await _close_adapters(source_client, embedding_model)

    engine = create_engine(settings.postgres)
    sessions = create_session_factory(engine)
    qdrant = create_qdrant_client(settings.qdrant)
    repository = SqlAlchemyKnowledgeIngestionRepository(sessions)
    vectors = QdrantKnowledgeVectorStore(qdrant, settings.qdrant.collection_name)
    try:
        await ensure_collection(qdrant, settings.qdrant)
        if arguments.command == "verify":
            verification_report = await verify_knowledge_base(
                manifest, repository, vectors, KnowledgeBM25Index()
            )
            _print_report(verification_report.model_dump(mode="json"))
            return 0 if verification_report.valid else 1

        source_client = _create_source_client(arguments, settings, manifest.allowed_domains)
        embedding_model = _create_embedding_model(arguments, settings)
        service = _create_service(settings, source_client, repository, vectors, embedding_model)
        ingestion_report = await service.ingest(
            manifest,
            dry_run=arguments.command == "dry-run",
            technology=arguments.technology,
            source_key=arguments.source_key,
        )
        _print_report(ingestion_report.model_dump(mode="json"))
        return 1 if any(item.outcome.value == "failed" for item in ingestion_report.results) else 0
    finally:
        if "source_client" in locals() and "embedding_model" in locals():
            await _close_adapters(source_client, embedding_model)
        await qdrant.close()
        await engine.dispose()


def _create_source_client(
    arguments: argparse.Namespace, settings: Settings, allowed_domains: tuple[str, ...]
) -> KnowledgeSourceClient:
    if arguments.fixture_dir:
        return FileKnowledgeSourceClient(arguments.fixture_dir)
    return HttpKnowledgeSourceClient(
        allowed_domains=set(allowed_domains),
        timeout_seconds=settings.knowledge_ingestion.request_timeout_seconds,
        max_bytes=settings.knowledge_ingestion.max_source_bytes,
        max_retries=settings.knowledge_ingestion.request_max_retries,
    )


def _create_embedding_model(arguments: argparse.Namespace, settings: Settings) -> EmbeddingModel:
    if arguments.offline_embeddings:
        return DeterministicEmbeddingModel(settings.qdrant.embedding_dimension)
    return OpenAICompatibleEmbeddingModel(settings.embeddings)


def _create_service(
    settings: Settings,
    source_client: KnowledgeSourceClient,
    repository: KnowledgeIngestionRepository,
    vectors: KnowledgeVectorStore,
    embedding_model: EmbeddingModel,
) -> NvidiaKnowledgeIngestionService:
    return NvidiaKnowledgeIngestionService(
        sources=source_client,
        preparer=DeterministicKnowledgePreparer(
            chunk_max_characters=settings.knowledge_ingestion.chunk_max_characters,
            chunk_overlap_characters=settings.knowledge_ingestion.chunk_overlap_characters,
        ),
        repository=repository,
        vectors=vectors,
        embeddings=embedding_model,
        embedding_dimension=settings.qdrant.embedding_dimension,
        embedding_fingerprint=(
            f"{settings.embeddings.provider}:{settings.embeddings.model}:"
            f"{settings.qdrant.embedding_dimension}"
        ),
        pipeline_version=settings.knowledge_ingestion.pipeline_version,
        embedding_batch_size=settings.knowledge_ingestion.embedding_batch_size,
        max_concurrency=settings.knowledge_ingestion.max_concurrency,
    )


async def _close_adapters(
    source_client: KnowledgeSourceClient, embedding_model: EmbeddingModel
) -> None:
    if isinstance(source_client, HttpKnowledgeSourceClient):
        await source_client.close()
    if isinstance(embedding_model, OpenAICompatibleEmbeddingModel):
        await embedding_model.close()


def _print_report(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    run()
