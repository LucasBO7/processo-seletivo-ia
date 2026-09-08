from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterator
from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.application.contracts.query_plan import QueryPlan
from app.application.ports.providers import ChatModel
from app.core.config import QueryPlannerConfig, Settings
from app.core.resources import ApplicationResources
from app.graph.agents.query_planner import QueryPlannerAgent
from app.graph.model_policy import ModelRegistry
from app.graph.state import AppState
from tests.fakes.providers import FakeChatModel

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(autouse=True)
def block_live_llm_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make accidental paid/network LLM use fail before a client is created."""

    def blocked_client(**_: object) -> None:
        raise AssertionError("Live LLM clients are forbidden in automated tests.")

    monkeypatch.setattr("app.infrastructure.providers.groq.ChatGroq", blocked_client)
    monkeypatch.setattr("app.infrastructure.providers.cohere.cohere.AsyncClientV2", blocked_client)
    monkeypatch.setattr("app.api.app.OpenAICompatibleEmbeddingModel", blocked_client)


@pytest.fixture(autouse=True)
def block_unapproved_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow real network only in explicitly enabled integration/external runs."""
    import os

    if os.getenv("RUN_INTEGRATION_TESTS") == "1" or os.getenv("RUN_EXTERNAL_TESTS") == "1":
        return

    async def blocked_request(*_: object, **__: object) -> None:
        raise AssertionError("Real network is forbidden in automated tests.")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked_request)


class StubWorkflow:
    def __init__(self, result: AppState | None = None) -> None:
        self.result = result
        self.calls: list[AppState] = []

    async def ainvoke(self, state: AppState) -> AppState:
        self.calls.append(state.copy())
        if self.result is not None:
            return AppState({**state, **self.result})
        plan = QueryPlan.model_validate(
            {
                "status": "ready",
                "normalized_query": state["query"],
                "filters": {},
                "analysis_strategy": {
                    "mode": "exploratory",
                    "objectives": ["descobrir startups"],
                    "rationale": "Consulta ampla e executável.",
                },
                "ambiguities": [],
                "clarification_questions": [],
            }
        )
        return AppState({**state, "query_plan": plan})


class StubResources:
    def __init__(
        self, model: ChatModel | None = None, workflow: StubWorkflow | None = None
    ) -> None:
        default_response = json.dumps(
            {
                "status": "ready",
                "normalized_query": "startups",
                "filters": {},
                "analysis_strategy": {
                    "mode": "exploratory",
                    "objectives": ["descobrir startups"],
                    "rationale": "Consulta ampla e executável.",
                },
                "ambiguities": [],
                "clarification_questions": [],
            }
        )
        self.chat_model = model or FakeChatModel(default_response)
        self.model_registry = ModelRegistry(
            llm_fast=self.chat_model,
            llm_heavy=self.chat_model,
        )
        self.query_planner = QueryPlannerAgent(
            model=self.chat_model,
            config=QueryPlannerConfig(),
        )
        self.extractor = None
        self.startup_classifier = None
        self.evidence_validator = None
        self.recommendation = None
        self.briefing = None
        self.workflow = workflow or StubWorkflow()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:password@localhost:5432/database"},
        qdrant={"url": "http://localhost:6333", "embedding_dimension": 4},
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    resources = StubResources()

    async def factory(_: Settings) -> ApplicationResources:
        return cast(ApplicationResources, resources)

    app = create_app(settings, resource_factory=factory)
    with TestClient(app) as test_client:
        yield test_client
    assert resources.closed
