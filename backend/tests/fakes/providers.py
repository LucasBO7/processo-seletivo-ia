from __future__ import annotations

from collections.abc import Sequence

from app.application.ports.providers import ChatMessage, RankedDocument


class FakeChatModel:
    def __init__(self, response: str = "resposta determinística") -> None:
        self.response = response
        self.calls: list[Sequence[ChatMessage]] = []

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(messages)
        return self.response


class SequenceChatModel:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.calls: list[Sequence[ChatMessage]] = []

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeEmbeddingModel:
    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(index + 1)] * self.dimension for index, _ in enumerate(texts)]


class FakeReranker:
    async def rerank(
        self,
        query: str,
        documents: Sequence[RankedDocument],
        *,
        top_n: int,
    ) -> list[RankedDocument]:
        del query
        return sorted(documents, key=lambda item: item.score, reverse=True)[:top_n]
