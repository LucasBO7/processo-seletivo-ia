from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.application.contracts.knowledge_ingestion import (
    KnowledgeContentType,
    KnowledgeSource,
    NvidiaTechnology,
)
from app.core.config import ModelProviderConfig
from app.domain.models import KnowledgeChunk
from app.infrastructure.ingestion.http_source import HttpKnowledgeSourceClient
from app.infrastructure.providers.embeddings import OpenAICompatibleEmbeddingModel
from app.infrastructure.retrieval.knowledge_bm25 import KnowledgeBM25Index
from app.infrastructure.vector.knowledge import QdrantKnowledgeVectorStore


def source() -> KnowledgeSource:
    return KnowledgeSource(
        source_key="cuda",
        technology=NvidiaTechnology.CUDA,
        canonical_url="https://developer.nvidia.com/cuda-toolkit",
        content_type=KnowledgeContentType.HTML,
        extractor="web",
    )


async def test_http_adapter_uses_injected_transport_without_network() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<h1>CUDA</h1>",
            request=request,
        )
    )
    client = httpx.AsyncClient(transport=transport)
    adapter = HttpKnowledgeSourceClient(
        allowed_domains={"developer.nvidia.com"},
        timeout_seconds=1,
        max_bytes=1000,
        client=client,
    )

    fetched = await adapter.fetch(source())

    assert fetched.body == "<h1>CUDA</h1>"
    await client.aclose()


async def test_http_adapter_blocks_redirect_outside_allowlist() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302, headers={"location": "https://example.com/trap"}, request=request
        )
    )
    client = httpx.AsyncClient(transport=transport)
    adapter = HttpKnowledgeSourceClient(
        allowed_domains={"developer.nvidia.com"},
        timeout_seconds=1,
        max_bytes=1000,
        client=client,
    )

    with pytest.raises(ValueError, match="knowledge_source_invalid"):
        await adapter.fetch(source())
    await client.aclose()


async def test_embedding_adapter_validates_fake_response_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 1]},
                    {"index": 0, "embedding": [1, 0]},
                ]
            },
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = ModelProviderConfig(
        provider="compatible",
        model="tiny",
        base_url="https://api.nvidia.com/v1/",
        api_key="fake",
    )
    adapter = OpenAICompatibleEmbeddingModel(config, client=client)

    assert await adapter.embed(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]
    await client.aclose()


def test_knowledge_bm25_search_preserves_chunk_ids() -> None:
    document_id = uuid4()
    relevant = KnowledgeChunk(
        id=uuid4(),
        document_id=document_id,
        content="CUDA GPU acceleration CUDA",
        chunk_index=0,
        content_hash="a" * 64,
    )
    other = KnowledgeChunk(
        id=uuid4(),
        document_id=document_id,
        content="voice transcription",
        chunk_index=1,
        content_hash="b" * 64,
    )
    third = KnowledgeChunk(
        id=uuid4(),
        document_id=document_id,
        content="digital twins and simulation",
        chunk_index=2,
        content_hash="c" * 64,
    )

    result = KnowledgeBM25Index().search("CUDA acceleration", [other, relevant, third], limit=1)

    assert result[0].chunk_id == relevant.id
    assert result[0].score > 0


async def test_qdrant_search_returns_only_ids_and_scores() -> None:
    chunk_id = uuid4()

    class FakeQdrant:
        async def query_points(self, **kwargs: object) -> SimpleNamespace:
            assert kwargs["collection_name"] == "knowledge"
            assert kwargs["query"] == [0.1, 0.2]
            assert kwargs["with_payload"] is False
            assert kwargs["with_vectors"] is False
            return SimpleNamespace(points=[SimpleNamespace(id=str(chunk_id), score=0.75)])

    adapter = QdrantKnowledgeVectorStore(FakeQdrant(), "knowledge")  # type: ignore[arg-type]

    result = await adapter.search([0.1, 0.2], limit=5)

    assert result[0].chunk_id == chunk_id
    assert result[0].score == 0.75
