from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.application.contracts.extraction import ExtractorOutput
from app.application.ports.providers import ChatModelError, ChatModelErrorCode
from app.core.config import ExtractorConfig
from app.domain.models import SourceReference
from app.graph.agents.extractor import ExtractorAgent, create_extractor_agent
from app.graph.model_policy import ModelRegistry
from app.graph.prompts.extractor import build_messages
from app.graph.state import AppState
from tests.fakes.providers import FakeChatModel, SequenceChatModel


def source_for(
    startup_id: UUID, *, excerpt: str = "Acme sells fraud detection software."
) -> SourceReference:
    return SourceReference(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/acme",
        title="Acme profile",
        excerpt=excerpt,
    )


def output_for(source: SourceReference, **overrides: object) -> str:
    citation = {
        "startup_id": str(source.startup_id),
        "source_id": str(source.source_id),
        "source_url": source.source_url,
    }
    payload: dict[str, object] = {
        "product": {"value": "Fraud detection software", "sources": [citation]},
        "business_model": None,
        "sector": None,
        "target_audience": None,
        "ai_use_cases": [],
        "technologies": [],
        "infrastructure": [],
        "external_dependencies": [],
        "technical_needs": [],
        "claims": [],
        "unknown_fields": [
            "business_model",
            "sector",
            "target_audience",
            "ai_use_cases",
            "technologies",
            "infrastructure",
            "external_dependencies",
            "technical_needs",
            "claims",
        ],
    }
    payload.update(overrides)
    return json.dumps(payload)


def state_for(startup_id: UUID, sources: list[SourceReference]) -> AppState:
    return AppState(
        candidate_startups=[{"startup_id": startup_id, "name": "Acme", "score": 2.0}],
        selected_sources=sources,
        structured_profiles=[],
        warnings=[],
        errors=[],
        metrics={"retriever_duration_ms": 1.0},
    )


def test_contract_rejects_extra_fields_and_unknown_fields_with_facts() -> None:
    startup_id = uuid4()
    source = source_for(startup_id)

    with pytest.raises(ValidationError):
        ExtractorOutput.model_validate_json(output_for(source, invented="value"))
    with pytest.raises(ValidationError):
        ExtractorOutput.model_validate_json(output_for(source, unknown_fields=["product"]))


def test_prompt_requires_exhaustive_extraction_of_explicit_technical_needs() -> None:
    startup_id = uuid4()
    source = source_for(
        startup_id,
        excerpt="The product needs to reduce inference latency.",
    )

    system_prompt, _ = build_messages(startup_name="Acme", sources=[source])

    assert "every profile field" in system_prompt
    assert "reducing latency" in system_prompt
    assert "must not be recommendations" in system_prompt


@pytest.mark.asyncio
async def test_extractor_builds_traceable_profile_and_metrics() -> None:
    startup_id = uuid4()
    source = source_for(startup_id)
    model = FakeChatModel(output_for(source))
    agent = ExtractorAgent(model=model, config=ExtractorConfig())

    result = await agent(state_for(startup_id, [source]))

    profile = result["structured_profiles"][0]
    assert profile.startup_id == startup_id
    assert profile.name == "Acme"
    assert profile.product is not None
    assert profile.product.sources[0].source_id == source.source_id
    assert profile.product.sources[0].source_url == source.source_url
    assert profile.business_model is None
    assert result["metrics"]["extractor_profile_count"] == 1.0
    assert result["metrics"]["extractor_model_call_count"] == 1.0
    assert result["metrics"]["retriever_duration_ms"] == 1.0
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_extractor_repairs_invalid_source_reference_once() -> None:
    startup_id = uuid4()
    source = source_for(startup_id)
    invalid = output_for(source).replace(str(source.source_id), str(uuid4()))
    model = SequenceChatModel([invalid, output_for(source)])
    agent = ExtractorAgent(model=model, config=ExtractorConfig())

    result = await agent(state_for(startup_id, [source]))

    assert len(result["structured_profiles"]) == 1
    assert result["errors"] == []
    assert result["metrics"]["extractor_repair_count"] == 1.0
    assert len(model.calls) == 2
    assert str(source.source_id) in model.calls[1][1].content


@pytest.mark.asyncio
@pytest.mark.parametrize("as_singleton_list", [False, True])
async def test_extractor_normalizes_redundant_output_shape(as_singleton_list: bool) -> None:
    startup_id = uuid4()
    source = source_for(startup_id)
    payload = json.loads(output_for(source))
    payload["external_dependencies"] = None
    payload["unknown_fields"] = []
    candidate = json.dumps([payload] if as_singleton_list else payload)

    result = await ExtractorAgent(model=FakeChatModel(candidate), config=ExtractorConfig())(
        state_for(startup_id, [source])
    )

    profile = result["structured_profiles"][0]
    assert profile.external_dependencies == []
    assert "external_dependencies" in profile.unknown_fields
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_extractor_deduplicates_facts_and_orders_citations() -> None:
    startup_id = uuid4()
    first = source_for(startup_id)
    second = SourceReference(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/second",
        title="Second",
        excerpt="Acme uses computer vision.",
    )
    first_ref = {
        "startup_id": str(first.startup_id),
        "source_id": str(first.source_id),
        "source_url": first.source_url,
    }
    second_ref = {
        "startup_id": str(second.startup_id),
        "source_id": str(second.source_id),
        "source_url": second.source_url,
    }
    facts = [
        {"value": "Computer vision", "sources": [second_ref, first_ref, second_ref]},
        {"value": " computer   vision ", "sources": [first_ref]},
    ]
    model = FakeChatModel(
        output_for(
            first,
            ai_use_cases=facts,
            unknown_fields=[
                "business_model",
                "sector",
                "target_audience",
                "technologies",
                "infrastructure",
                "external_dependencies",
                "technical_needs",
                "claims",
            ],
        )
    )

    result = await ExtractorAgent(model=model, config=ExtractorConfig())(
        state_for(startup_id, [first, second])
    )

    use_cases = result["structured_profiles"][0].ai_use_cases
    assert len(use_cases) == 1
    assert [item.source_id for item in use_cases[0].sources] == [
        first.source_id,
        second.source_id,
    ]


@pytest.mark.asyncio
async def test_extractor_rejects_invalid_output_after_repair() -> None:
    startup_id = uuid4()
    source = source_for(startup_id)
    model = SequenceChatModel(["not-json", "still-not-json"])
    agent = ExtractorAgent(model=model, config=ExtractorConfig())

    result = await agent(state_for(startup_id, [source]))

    assert result["structured_profiles"] == []
    assert result["errors"][0].code == "extractor_invalid_output"
    assert result["errors"][0].message == (
        "The extractor could not produce a usable startup profile."
    )
    assert result["metrics"]["extractor_failure_count"] == 1.0


@pytest.mark.asyncio
async def test_extractor_sanitizes_provider_failure() -> None:
    startup_id = uuid4()
    source = source_for(startup_id)
    model = SequenceChatModel(
        [ChatModelError(ChatModelErrorCode.UNAVAILABLE, "secret-provider-detail")]
    )
    agent = ExtractorAgent(model=model, config=ExtractorConfig())

    result = await agent(state_for(startup_id, [source]))

    assert result["errors"][0].code == "extractor_unavailable"
    assert "secret-provider-detail" not in result["errors"][0].message


@pytest.mark.asyncio
async def test_extractor_preserves_completed_profile_before_provider_failure() -> None:
    first_id = uuid4()
    second_id = uuid4()
    first = source_for(first_id)
    second = source_for(second_id)
    model = SequenceChatModel(
        [
            output_for(first),
            ChatModelError(ChatModelErrorCode.UNAVAILABLE, "private-detail"),
        ]
    )
    state = state_for(first_id, [first, second])
    state["candidate_startups"].append({"startup_id": second_id, "name": "Beta", "score": 1.0})

    result = await ExtractorAgent(model=model, config=ExtractorConfig())(state)

    assert [profile.startup_id for profile in result["structured_profiles"]] == [first_id]
    assert result["errors"][0].code == "extractor_unavailable"
    assert result["metrics"]["extractor_profile_count"] == 1.0


@pytest.mark.asyncio
async def test_extractor_logs_only_operational_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    startup_id = uuid4()
    source = source_for(startup_id, excerpt="sensitive-document-content")
    model = FakeChatModel(output_for(source))

    with caplog.at_level(logging.INFO, logger="app.graph.agents.extractor"):
        await ExtractorAgent(model=model, config=ExtractorConfig())(state_for(startup_id, [source]))

    log_text = caplog.text
    assert "extractor_completed" in log_text
    assert "sensitive-document-content" not in log_text
    assert source.source_url not in log_text
    assert model.response not in log_text


@pytest.mark.asyncio
async def test_extractor_skips_unsourced_candidate_and_warns() -> None:
    sourced_id = uuid4()
    unsourced_id = uuid4()
    source = source_for(sourced_id)
    model = FakeChatModel(output_for(source))
    agent = ExtractorAgent(model=model, config=ExtractorConfig())
    state = state_for(sourced_id, [source])
    state["candidate_startups"].append(
        {"startup_id": unsourced_id, "name": "No Source", "score": 1.0}
    )

    result = await agent(state)

    assert [profile.startup_id for profile in result["structured_profiles"]] == [sourced_id]
    assert "extractor_sources_missing" in result["warnings"]
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_extractor_limits_context_and_reports_truncation() -> None:
    startup_id = uuid4()
    first = source_for(startup_id, excerpt="A" * 80)
    second = SourceReference(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/second",
        title="Second",
        excerpt="B" * 80,
    )
    model = FakeChatModel(output_for(first))
    config = ExtractorConfig(max_sources_per_startup=2, max_context_characters=100)
    agent = ExtractorAgent(model=model, config=config)

    result = await agent(state_for(startup_id, [first, second]))

    assert "extractor_context_truncated" in result["warnings"]
    assert result["metrics"]["extractor_source_count"] == 2.0
    prompt = model.calls[0][1].content
    assert '"excerpt":' in prompt
    assert "B" * 20 in prompt
    assert "B" * 21 not in prompt


def test_extractor_factory_uses_fast_model() -> None:
    fast = FakeChatModel()
    heavy = FakeChatModel()

    agent = create_extractor_agent(
        registry=ModelRegistry(llm_fast=fast, llm_heavy=heavy),
        config=ExtractorConfig(),
    )

    assert agent._model is fast
