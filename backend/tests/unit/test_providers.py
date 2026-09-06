from __future__ import annotations

from app.application.ports.providers import ChatMessage, RankedDocument
from tests.fakes.providers import FakeChatModel, FakeEmbeddingModel, FakeReranker


async def test_provider_fakes_are_deterministic() -> None:
    chat = FakeChatModel("ok")
    embeddings = FakeEmbeddingModel(dimension=2)
    reranker = FakeReranker()
    documents = [
        RankedDocument(document_id="low", text="A", score=0.1),
        RankedDocument(document_id="high", text="B", score=0.9),
    ]

    assert await chat.complete([ChatMessage(role="user", content="teste")]) == "ok"
    assert await embeddings.embed(["a", "b"]) == [[1.0, 1.0], [2.0, 2.0]]
    assert (await reranker.rerank("q", documents, top_n=1))[0].document_id == "high"
