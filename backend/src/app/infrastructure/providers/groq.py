from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Protocol, cast

from groq import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError
from groq import RateLimitError as GroqRateLimitError
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.application.ports.providers import (
    ChatMessage,
    ChatModel,
    ChatModelError,
    ChatModelErrorCode,
)
from app.core.config import LLMProfileConfig

logger = logging.getLogger(__name__)


class AsyncChatClient(Protocol):
    async def ainvoke(self, messages: Sequence[BaseMessage]) -> AIMessage: ...


def _to_langchain_message(message: ChatMessage) -> BaseMessage:
    if message.role == "system":
        return SystemMessage(content=message.content)
    if message.role in {"user", "human"}:
        return HumanMessage(content=message.content)
    if message.role in {"assistant", "ai"}:
        return AIMessage(content=message.content)
    raise ChatModelError(
        ChatModelErrorCode.INVALID_MESSAGE,
        "Chat message role is not supported.",
    )


def _provider_error_code(error: Exception) -> ChatModelErrorCode:
    if isinstance(error, AuthenticationError):
        return ChatModelErrorCode.AUTHENTICATION_FAILED
    if isinstance(error, GroqRateLimitError):
        return ChatModelErrorCode.RATE_LIMITED
    if isinstance(error, APITimeoutError):
        return ChatModelErrorCode.TIMEOUT
    if isinstance(error, (APIConnectionError, APIStatusError)):
        return ChatModelErrorCode.UNAVAILABLE
    return ChatModelErrorCode.UNAVAILABLE


class GroqChatModel:
    def __init__(self, *, client: AsyncChatClient, profile: str, model: str) -> None:
        self._client = client
        self._profile = profile
        self._model = model

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        started_at = time.perf_counter()
        try:
            converted = [_to_langchain_message(message) for message in messages]
            response = await self._client.ainvoke(converted)
            if not isinstance(response.content, str):
                raise ChatModelError(ChatModelErrorCode.INVALID_RESPONSE)
        except ChatModelError as error:
            self._log_failure(error.code, started_at)
            raise
        except Exception as error:
            sanitized = ChatModelError(_provider_error_code(error))
            self._log_failure(sanitized.code, started_at)
            raise sanitized from None

        logger.info(
            "chat_model_request_completed",
            extra={
                "profile": self._profile,
                "model": self._model,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
                "result": "success",
            },
        )
        return response.content

    def _log_failure(self, code: ChatModelErrorCode, started_at: float) -> None:
        logger.warning(
            "chat_model_request_failed",
            extra={
                "profile": self._profile,
                "model": self._model,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
                "result": "error",
                "error_code": code,
            },
        )


def create_groq_chat_model(
    *,
    config: LLMProfileConfig,
    api_key: str | None,
    profile: str,
) -> ChatModel:
    if not api_key:
        raise ChatModelError(
            ChatModelErrorCode.CONFIGURATION_INVALID,
            "GROQ__API_KEY is required to configure Groq chat models.",
        )
    client = ChatGroq(
        model_name=config.model,
        temperature=config.temperature,
        api_key=api_key,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries,
    )
    return GroqChatModel(
        client=cast(AsyncChatClient, client),
        profile=profile,
        model=config.model,
    )
