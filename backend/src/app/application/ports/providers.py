from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class RankedDocument:
    document_id: str
    text: str
    score: float


class ChatModel(Protocol):
    async def complete(self, messages: Sequence[ChatMessage]) -> str: ...


class EmbeddingModel(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    async def rerank(
        self,
        query: str,
        documents: Sequence[RankedDocument],
        *,
        top_n: int,
    ) -> list[RankedDocument]: ...
