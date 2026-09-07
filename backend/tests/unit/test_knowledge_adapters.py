from __future__ import annotations

import httpx
import pytest

from app.application.contracts.knowledge_ingestion import (
    KnowledgeContentType,
    KnowledgeSource,
    NvidiaTechnology,
)
from app.core.config import ModelProviderConfig
from app.infrastructure.ingestion.http_source import HttpKnowledgeSourceClient
from app.infrastructure.providers.embeddings import OpenAICompatibleEmbeddingModel


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
