from __future__ import annotations

import pytest

from app.api.app import create_model_registry, create_resources
from app.application.ports.providers import ChatMessage, ChatModel, RankedDocument
from app.core.config import LLMProfileConfig, Settings
from app.graph.model_policy import ModelProfile, ModelRegistry
from app.graph.state import AppState
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


def test_composition_builds_each_shared_model_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[LLMProfileConfig, str | None, str]] = []

    def factory(*, config: LLMProfileConfig, api_key: str | None, profile: str) -> ChatModel:
        calls.append((config, api_key, profile))
        return FakeChatModel(profile)

    monkeypatch.setattr("app.api.app.create_groq_chat_model", factory)
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:password@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
        groq={"api_key": "groq-secret"},
    )

    registry = create_model_registry(settings)

    assert len(calls) == 2
    assert calls[0] == (settings.llm_fast, "groq-secret", ModelProfile.FAST)
    assert calls[1] == (settings.llm_heavy, "groq-secret", ModelProfile.HEAVY)
    assert registry.llm_fast is not registry.llm_heavy


async def test_application_resources_expose_the_shared_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fast = FakeChatModel("fast")
    heavy = FakeChatModel("heavy")
    registry = ModelRegistry(llm_fast=fast, llm_heavy=heavy)
    workflow_calls = 0
    compiled_query_planner: object | None = None
    compiled_extractor: object | None = None
    compiled_startup_classifier: object | None = None

    class StubWorkflow:
        async def ainvoke(self, state: AppState) -> AppState:
            return state

    workflow = StubWorkflow()

    def compile_workflow(**components: object) -> StubWorkflow:
        nonlocal compiled_extractor, compiled_query_planner, compiled_startup_classifier
        nonlocal workflow_calls
        workflow_calls += 1
        compiled_query_planner = components["query_planner"]
        compiled_extractor = components["extractor"]
        compiled_startup_classifier = components["startup_classifier"]
        return workflow

    class StubEngine:
        async def dispose(self) -> None:
            return None

    class StubQdrant:
        async def close(self) -> None:
            return None

    async def ensure_collection(*_: object) -> None:
        return None

    monkeypatch.setattr("app.api.app.create_model_registry", lambda _: registry)
    monkeypatch.setattr("app.api.app.create_engine", lambda _: StubEngine())
    monkeypatch.setattr("app.api.app.create_session_factory", lambda _: object())
    monkeypatch.setattr("app.api.app.create_qdrant_client", lambda _: StubQdrant())
    monkeypatch.setattr("app.api.app.ensure_collection", ensure_collection)
    monkeypatch.setattr("app.api.app.DatabaseReadinessProbe", lambda _: object())
    monkeypatch.setattr("app.api.app.QdrantReadinessProbe", lambda _: object())
    monkeypatch.setattr("app.api.app.compile_analysis_workflow", compile_workflow)
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:password@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
        groq={"api_key": "groq-secret"},
    )

    resources = await create_resources(settings)

    assert resources.llm_fast is fast
    assert resources.llm_heavy is heavy
    assert resources.model_registry is registry
    assert resources.query_planner is compiled_query_planner
    assert resources.extractor is compiled_extractor
    assert resources.startup_classifier is compiled_startup_classifier
    assert resources.workflow is workflow
    assert workflow_calls == 1
