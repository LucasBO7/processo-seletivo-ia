from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, cast

import httpx
import pytest
from groq import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError
from langchain_core.messages import AIMessage, BaseMessage

from app.application.ports.providers import ChatMessage, ChatModelError, ChatModelErrorCode
from app.core.config import LLMProfileConfig
from app.infrastructure.providers.groq import (
    GroqChatModel,
    GroqRequestLimiter,
    create_groq_chat_model,
)


class FakeAsyncChatClient:
    def __init__(self, response: AIMessage | Exception) -> None:
        self.response = response
        self.calls: list[Sequence[BaseMessage]] = []

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.calls.append(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


async def test_adapter_converts_messages_and_returns_text(caplog: pytest.LogCaptureFixture) -> None:
    client = FakeAsyncChatClient(AIMessage(content="structured result"))
    model = GroqChatModel(client=client, profile="fast", model="configured-model")

    with caplog.at_level(logging.INFO):
        result = await model.complete(
            [
                ChatMessage(role="system", content="system data"),
                ChatMessage(role="user", content="private query"),
                ChatMessage(role="assistant", content="previous result"),
            ]
        )

    assert result == "structured result"
    assert [message.type for message in client.calls[0]] == ["system", "human", "ai"]
    assert "private query" not in caplog.text
    assert "structured result" not in caplog.text
    record = cast(Any, caplog.records[-1])
    assert record.model == "configured-model"
    assert record.profile == "fast"


async def test_adapter_rejects_unknown_role_without_calling_client() -> None:
    client = FakeAsyncChatClient(AIMessage(content="unused"))
    model = GroqChatModel(client=client, profile="fast", model="model")

    with pytest.raises(ChatModelError) as error:
        await model.complete([ChatMessage(role="tool", content="unsafe")])

    assert error.value.code is ChatModelErrorCode.INVALID_MESSAGE
    assert client.calls == []


async def test_shared_limiter_spaces_requests_across_profiles() -> None:
    now = 100.0
    waits: list[float] = []

    def clock() -> float:
        return now

    async def sleep(delay: float) -> None:
        nonlocal now
        waits.append(delay)
        now += delay

    limiter = GroqRequestLimiter(7, clock=clock, sleep=sleep)
    fast_client = FakeAsyncChatClient(AIMessage(content="fast"))
    heavy_client = FakeAsyncChatClient(AIMessage(content="heavy"))
    fast = GroqChatModel(
        client=fast_client,
        profile="fast",
        model="fast-model",
        request_limiter=limiter,
    )
    heavy = GroqChatModel(
        client=heavy_client,
        profile="heavy",
        model="heavy-model",
        request_limiter=limiter,
    )

    assert await fast.complete([ChatMessage(role="user", content="first")]) == "fast"
    assert await heavy.complete([ChatMessage(role="user", content="second")]) == "heavy"

    assert waits == [7]
    assert len(fast_client.calls) == 1
    assert len(heavy_client.calls) == 1


async def test_adapter_rejects_non_text_response() -> None:
    response = AIMessage(content=[{"type": "text", "text": "not accepted"}])
    model = GroqChatModel(client=FakeAsyncChatClient(response), profile="fast", model="model")

    with pytest.raises(ChatModelError) as error:
        await model.complete([ChatMessage(role="user", content="query")])

    assert error.value.code is ChatModelErrorCode.INVALID_RESPONSE


def _response_error(error_type: type[AuthenticationError | RateLimitError]) -> Exception:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(401, request=request)
    return error_type("provider-secret", response=response, body={"secret": "raw"})


@pytest.mark.parametrize(
    ("provider_error", "expected_code"),
    [
        (_response_error(AuthenticationError), ChatModelErrorCode.AUTHENTICATION_FAILED),
        (_response_error(RateLimitError), ChatModelErrorCode.RATE_LIMITED),
        (
            APITimeoutError(httpx.Request("POST", "https://api.groq.com")),
            ChatModelErrorCode.TIMEOUT,
        ),
        (
            APIConnectionError(request=httpx.Request("POST", "https://api.groq.com")),
            ChatModelErrorCode.UNAVAILABLE,
        ),
        (RuntimeError("provider-secret"), ChatModelErrorCode.UNAVAILABLE),
    ],
)
async def test_adapter_sanitizes_provider_failures(
    provider_error: Exception,
    expected_code: ChatModelErrorCode,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model = GroqChatModel(
        client=FakeAsyncChatClient(provider_error), profile="heavy", model="model"
    )

    with caplog.at_level(logging.WARNING), pytest.raises(ChatModelError) as error:
        await model.complete([ChatMessage(role="user", content="private-query")])

    assert error.value.code is expected_code
    assert "provider-secret" not in str(error.value)
    assert "provider-secret" not in caplog.text
    assert "private-query" not in caplog.text


def test_factory_requires_api_key_before_creating_client() -> None:
    config = LLMProfileConfig(model="model", temperature=0)

    with pytest.raises(ChatModelError) as error:
        create_groq_chat_model(config=config, api_key=None, profile="fast")

    assert error.value.code is ChatModelErrorCode.CONFIGURATION_INVALID
    assert "GROQ__API_KEY" in str(error.value)


def test_automated_tests_block_live_llm_client_creation() -> None:
    config = LLMProfileConfig(model="model", temperature=0)

    with pytest.raises(AssertionError, match="Live LLM clients are forbidden"):
        create_groq_chat_model(config=config, api_key="must-not-be-used", profile="fast")


def test_factory_builds_configured_client_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def chat_groq_factory(**kwargs: object) -> FakeAsyncChatClient:
        captured.update(kwargs)
        return FakeAsyncChatClient(AIMessage(content="unused"))

    monkeypatch.setattr("app.infrastructure.providers.groq.ChatGroq", chat_groq_factory)
    config = LLMProfileConfig(
        model="configured-model",
        temperature=0.2,
        timeout_seconds=14,
        max_retries=1,
        max_tokens=4_096,
    )

    model = create_groq_chat_model(
        config=config,
        api_key="private-key",
        profile="fast",
    )

    assert isinstance(model, GroqChatModel)
    assert captured == {
        "model_name": "configured-model",
        "temperature": 0.2,
        "max_tokens": 4_096,
        "model_kwargs": {"response_format": {"type": "json_object"}},
        "api_key": "private-key",
        "timeout": 14,
        "max_retries": 1,
    }
