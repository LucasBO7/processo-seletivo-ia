from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.application.ports.providers import ChatModel
from app.core.config import Settings
from app.core.resources import ApplicationResources
from app.graph.model_policy import ModelRegistry
from tests.fakes.providers import FakeChatModel

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class StubResources:
    def __init__(self, model: ChatModel | None = None) -> None:
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
