from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


class ChatModelErrorCode(StrEnum):
    AUTHENTICATION_FAILED = "chat_model_authentication_failed"
    CONFIGURATION_INVALID = "chat_model_configuration_invalid"
    INVALID_MESSAGE = "chat_model_invalid_message"
    INVALID_RESPONSE = "chat_model_invalid_response"
    MODEL_NOT_ALLOCATED = "chat_model_not_allocated"
    RATE_LIMITED = "chat_model_rate_limited"
    TIMEOUT = "chat_model_timeout"
    UNAVAILABLE = "chat_model_unavailable"


class ChatModelError(RuntimeError):
    """Provider-independent, sanitized chat-model failure."""

    def __init__(
        self, code: ChatModelErrorCode, message: str = "Chat model request failed."
    ) -> None:
        self.code = code
        super().__init__(message)


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
