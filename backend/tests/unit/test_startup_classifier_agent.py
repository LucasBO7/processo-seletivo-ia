from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.application.contracts.classification import (
    ClassificationStatus,
    ClassifierOutput,
    ConfidenceLevel,
)
from app.application.contracts.extraction import (
    ExtractedFact,
    ExtractionSource,
    ProfileField,
    StructuredStartupProfile,
)
from app.application.ports.providers import ChatModelError, ChatModelErrorCode
from app.core.config import StartupClassifierConfig
from app.domain.models import AIMaturity, SourceReference
from app.graph.agents.startup_classifier import (
    StartupClassifierAgent,
    create_startup_classifier_agent,
)
from app.graph.model_policy import ModelRegistry
from app.graph.state import AppState
from tests.fakes.providers import FakeChatModel, SequenceChatModel


def source_for(
    startup_id: UUID, *, excerpt: str = "AI detects fraud in real time."
) -> SourceReference:
    return SourceReference(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/acme",
        title="Acme product",
        excerpt=excerpt,
    )


def extraction_source(source: SourceReference) -> ExtractionSource:
    return ExtractionSource(
        startup_id=source.startup_id,
        source_id=source.source_id,
        source_url=source.source_url,
    )


def profile_for(source: SourceReference) -> StructuredStartupProfile:
    return StructuredStartupProfile(
        startup_id=source.startup_id,
        name="Acme",
        product=ExtractedFact(
            value="AI fraud detection platform", sources=[extraction_source(source)]
        ),
        ai_use_cases=[ExtractedFact(value="Detects fraud", sources=[extraction_source(source)])],
        unknown_fields=[
            field
            for field in ProfileField
            if field not in {ProfileField.PRODUCT, ProfileField.AI_USE_CASES}
        ],
    )


def empty_profile(startup_id: UUID) -> StructuredStartupProfile:
    return StructuredStartupProfile(
        startup_id=startup_id,
        name="Unknown",
        unknown_fields=list(ProfileField),
    )


def model_output(
    source: SourceReference,
    *,
    category: str = "ai-native",
    signal_type: str = "core_ai_dependency",
) -> str:
    return json.dumps(
        {
            "status": "classified",
            "category": category,
            "justification": "The cited evidence makes AI central to the product.",
            "confidence": "high",
            "signals": [
                {
                    "type": signal_type,
                    "description": "AI performs the product's core fraud detection.",
                    "sources": [extraction_source(source).model_dump(mode="json")],
                }
            ],
        }
    )


def state_for(profile: StructuredStartupProfile, sources: list[SourceReference]) -> AppState:
    return AppState(
        structured_profiles=[profile],
        selected_sources=sources,
        classifications=[],
        warnings=[],
        errors=[],
        metrics={"extractor_duration_ms": 1.0},
    )


@pytest.mark.parametrize(
    ("category", "signal_type"),
    [
        ("ai-native", "core_ai_dependency"),
        ("ai-enabled", "supporting_ai_use"),
        ("non-ai", "explicit_non_ai"),
    ],
)
def test_contract_accepts_each_category_with_required_signal(
    category: str, signal_type: str
) -> None:
    source = source_for(uuid4())

    output = ClassifierOutput.model_validate_json(
        model_output(source, category=category, signal_type=signal_type)
    )

    assert output.category is AIMaturity(category)


def test_contract_rejects_forced_or_incoherent_classification() -> None:
    source = source_for(uuid4())
    payload = json.loads(model_output(source))
    payload["confidence"] = "low"
    with pytest.raises(ValidationError):
        ClassifierOutput.model_validate(payload)

    payload = json.loads(model_output(source, category="non-ai"))
    with pytest.raises(ValidationError):
        ClassifierOutput.model_validate(payload)

    payload = json.loads(model_output(source))
    payload["signals"].append(
        {
            "type": "conflicting_evidence",
            "description": "The evidence conflicts.",
            "sources": [extraction_source(source).model_dump(mode="json")],
        }
    )
    with pytest.raises(ValidationError):
        ClassifierOutput.model_validate(payload)


@pytest.mark.asyncio
async def test_classifier_produces_traceable_classification_and_metrics() -> None:
    source = source_for(uuid4())
    model = FakeChatModel(model_output(source))
    agent = StartupClassifierAgent(model=model, config=StartupClassifierConfig())

    result = await agent(state_for(profile_for(source), [source]))

    classification = result["classifications"][0]
    assert classification.startup_id == source.startup_id
    assert classification.name == "Acme"
    assert classification.category is AIMaturity.AI_NATIVE
    assert classification.evidence_references[0].source_id == source.source_id
    assert result["metrics"]["classifier_classification_count"] == 1.0
    assert result["metrics"]["classifier_model_call_count"] == 1.0
    assert result["metrics"]["extractor_duration_ms"] == 1.0


@pytest.mark.asyncio
async def test_empty_profile_is_uncertain_without_model_call() -> None:
    startup_id = uuid4()
    model = FakeChatModel("must-not-be-used")

    result = await StartupClassifierAgent(model=model, config=StartupClassifierConfig())(
        state_for(empty_profile(startup_id), [])
    )

    classification = result["classifications"][0]
    assert classification.status is ClassificationStatus.UNCERTAIN
    assert classification.category is None
    assert classification.confidence is ConfidenceLevel.LOW
    assert classification.evidence_references == []
    assert "classifier_uncertain" in result["warnings"]
    assert model.calls == []


@pytest.mark.asyncio
async def test_profile_without_usable_source_is_uncertain_without_model_call() -> None:
    source = source_for(uuid4())
    model = FakeChatModel("must-not-be-used")

    result = await StartupClassifierAgent(model=model, config=StartupClassifierConfig())(
        state_for(profile_for(source), [])
    )

    assert result["classifications"][0].status is ClassificationStatus.UNCERTAIN
    assert model.calls == []


@pytest.mark.asyncio
async def test_classifier_repairs_invalid_reference_once() -> None:
    source = source_for(uuid4())
    invalid = model_output(source).replace(str(source.source_id), str(uuid4()))
    model = SequenceChatModel([invalid, model_output(source)])

    result = await StartupClassifierAgent(model=model, config=StartupClassifierConfig())(
        state_for(profile_for(source), [source])
    )

    assert len(result["classifications"]) == 1
    assert result["errors"] == []
    assert result["metrics"]["classifier_repair_count"] == 1.0
    assert str(source.source_id) in model.calls[1][1].content


@pytest.mark.asyncio
async def test_classifier_deduplicates_and_orders_evidence_references() -> None:
    startup_id = uuid4()
    first = source_for(startup_id)
    second = SourceReference(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/second",
        title="Second",
        excerpt="AI performs the core analysis.",
    )
    payload = json.loads(model_output(first))
    payload["signals"][0]["sources"] = [
        extraction_source(second).model_dump(mode="json"),
        extraction_source(first).model_dump(mode="json"),
        extraction_source(second).model_dump(mode="json"),
    ]
    model = FakeChatModel(json.dumps(payload))

    result = await StartupClassifierAgent(model=model, config=StartupClassifierConfig())(
        state_for(profile_for(first), [first, second])
    )

    classification = result["classifications"][0]
    assert [item.source_id for item in classification.signals[0].sources] == [
        first.source_id,
        second.source_id,
    ]
    assert [item.source_id for item in classification.evidence_references] == [
        first.source_id,
        second.source_id,
    ]


@pytest.mark.asyncio
async def test_classifier_returns_sanitized_invalid_output_error() -> None:
    source = source_for(uuid4())
    model = SequenceChatModel(["invalid", "still-invalid"])

    result = await StartupClassifierAgent(model=model, config=StartupClassifierConfig())(
        state_for(profile_for(source), [source])
    )

    assert result["classifications"] == []
    assert result["errors"][0].code == "classifier_invalid_output"
    assert result["metrics"]["classifier_failure_count"] == 1.0


@pytest.mark.asyncio
async def test_classifier_sanitizes_provider_failure() -> None:
    source = source_for(uuid4())
    model = SequenceChatModel(
        [ChatModelError(ChatModelErrorCode.UNAVAILABLE, "private-provider-detail")]
    )

    result = await StartupClassifierAgent(model=model, config=StartupClassifierConfig())(
        state_for(profile_for(source), [source])
    )

    assert result["errors"][0].code == "classifier_unavailable"
    assert "private-provider-detail" not in result["errors"][0].message


@pytest.mark.asyncio
async def test_classifier_preserves_completed_result_before_provider_failure() -> None:
    first = source_for(uuid4())
    second = source_for(uuid4())
    second_profile = profile_for(second).model_copy(update={"name": "Beta"})
    model = SequenceChatModel(
        [
            model_output(first),
            ChatModelError(ChatModelErrorCode.UNAVAILABLE, "private-detail"),
        ]
    )
    state = state_for(profile_for(first), [first, second])
    state["structured_profiles"].append(second_profile)

    result = await StartupClassifierAgent(model=model, config=StartupClassifierConfig())(state)

    assert [item.startup_id for item in result["classifications"]] == [first.startup_id]
    assert result["errors"][0].code == "classifier_unavailable"
    assert result["metrics"]["classifier_classification_count"] == 1.0


@pytest.mark.asyncio
async def test_classifier_limits_excerpt_context_and_warns() -> None:
    source = source_for(uuid4(), excerpt="A" * 150)
    model = FakeChatModel(model_output(source))
    config = StartupClassifierConfig(max_context_characters=100)

    result = await StartupClassifierAgent(model=model, config=config)(
        state_for(profile_for(source), [source])
    )

    assert "classifier_context_truncated" in result["warnings"]
    prompt = model.calls[0][1].content
    assert "A" * 100 in prompt
    assert "A" * 101 not in prompt


@pytest.mark.asyncio
async def test_classifier_logs_only_operational_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = source_for(uuid4(), excerpt="sensitive-classification-evidence")
    model = FakeChatModel(model_output(source))

    with caplog.at_level(logging.INFO, logger="app.graph.agents.startup_classifier"):
        await StartupClassifierAgent(model=model, config=StartupClassifierConfig())(
            state_for(profile_for(source), [source])
        )

    assert "startup_classifier_completed" in caplog.text
    assert "sensitive-classification-evidence" not in caplog.text
    assert source.source_url not in caplog.text
    assert model.response not in caplog.text


def test_classifier_factory_uses_heavy_model() -> None:
    fast = FakeChatModel()
    heavy = FakeChatModel()

    agent = create_startup_classifier_agent(
        registry=ModelRegistry(llm_fast=fast, llm_heavy=heavy),
        config=StartupClassifierConfig(),
    )

    assert agent._model is heavy
