from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.application.contracts.classification import (
    ClassificationSignal,
    ClassificationSignalType,
    ClassificationStatus,
    ConfidenceLevel,
    StartupClassification,
)
from app.application.contracts.evidence_validation import (
    ClaimAssessmentOutput,
    EvidenceStatus,
)
from app.application.contracts.extraction import (
    ExtractedFact,
    ExtractionSource,
    ProfileField,
    StructuredStartupProfile,
)
from app.application.ports.providers import ChatModelError, ChatModelErrorCode
from app.core.config import EvidenceValidatorConfig
from app.domain.models import AIMaturity, SourceReference
from app.graph.agents.evidence_validator import (
    EvidenceValidatorAgent,
    create_evidence_validator_agent,
)
from app.graph.model_policy import ModelRegistry
from app.graph.state import AppState
from tests.fakes.providers import FakeChatModel, SequenceChatModel


def source_for(startup_id: UUID, *, excerpt: str = "AI detects fraud.") -> SourceReference:
    return SourceReference(
        startup_id=startup_id,
        source_id=uuid4(),
        source_url="https://example.com/evidence",
        title="Evidence",
        excerpt=excerpt,
    )


def pointer(source: SourceReference) -> ExtractionSource:
    return ExtractionSource(
        startup_id=source.startup_id,
        source_id=source.source_id,
        source_url=source.source_url,
    )


def profile_for(source: SourceReference) -> StructuredStartupProfile:
    return StructuredStartupProfile(
        startup_id=source.startup_id,
        name="Acme",
        product=ExtractedFact(value="Fraud platform", sources=[pointer(source)]),
        technologies=[ExtractedFact(value="Python", sources=[pointer(source)])],
        unknown_fields=[
            field
            for field in ProfileField
            if field not in {ProfileField.PRODUCT, ProfileField.TECHNOLOGIES}
        ],
    )


def classification_for(source: SourceReference) -> StartupClassification:
    signal = ClassificationSignal(
        type=ClassificationSignalType.CORE_AI_DEPENDENCY,
        description="AI performs fraud detection.",
        sources=[pointer(source)],
    )
    return StartupClassification(
        startup_id=source.startup_id,
        name="Acme",
        status=ClassificationStatus.CLASSIFIED,
        category=AIMaturity.AI_NATIVE,
        justification="AI is central to fraud detection.",
        confidence=ConfidenceLevel.HIGH,
        signals=[signal],
        evidence_references=[pointer(source)],
    )


def assessment(
    source: SourceReference,
    key: str,
    *,
    status: str = "supported",
    verdict: str = "supports",
) -> dict[str, object]:
    return {
        "claim_key": key,
        "status": status,
        "justification": f"Documentary result for {key}.",
        "analyzed_sources": [
            {
                "startup_id": str(source.startup_id),
                "source_id": str(source.source_id),
                "source_url": source.source_url,
                "verdict": verdict,
            }
        ],
    }


def output(*items: dict[str, object]) -> str:
    return json.dumps({"assessments": list(items)})


def state_for(
    source: SourceReference,
    *,
    profile: StructuredStartupProfile | None = None,
    classification: StartupClassification | None = None,
) -> AppState:
    return AppState(
        structured_profiles=[profile or profile_for(source)],
        classifications=[classification or classification_for(source)],
        selected_sources=[source],
        warnings=[],
        errors=[],
        metrics={"classifier_duration_ms": 1.0},
    )


@pytest.mark.parametrize(
    ("status", "verdict"),
    [
        ("supported", "supports"),
        ("unsupported", "not_found"),
        ("insufficient", "not_found"),
    ],
)
def test_assessment_contract_accepts_coherent_statuses(status: str, verdict: str) -> None:
    source = source_for(uuid4())
    result = ClaimAssessmentOutput.model_validate(
        assessment(source, "product", status=status, verdict=verdict)
    )
    assert result.status is EvidenceStatus(status)


def test_assessment_contract_requires_support_and_contradiction_for_conflict() -> None:
    source = source_for(uuid4())
    payload = assessment(source, "product", status="conflicting")
    with pytest.raises(ValidationError):
        ClaimAssessmentOutput.model_validate(payload)

    second = source_for(source.startup_id)
    supporting_sources = assessment(source, "x")["analyzed_sources"]
    contradicting_sources = assessment(second, "x", verdict="contradicts")["analyzed_sources"]
    assert isinstance(supporting_sources, list)
    assert isinstance(contradicting_sources, list)
    payload["analyzed_sources"] = [
        supporting_sources[0],
        contradicting_sources[0],
    ]
    assert ClaimAssessmentOutput.model_validate(payload).status is EvidenceStatus.CONFLICTING


def test_enumerates_all_facts_in_contract_order() -> None:
    source = source_for(uuid4())

    items = EvidenceValidatorAgent.enumerate_claims(profile_for(source))

    assert [item.key for item in items] == ["product", "technologies[0]"]


@pytest.mark.asyncio
async def test_validator_filters_profile_and_preserves_diagnostics() -> None:
    source = source_for(uuid4())
    model = FakeChatModel(
        output(
            assessment(source, "product"),
            assessment(
                source,
                "technologies[0]",
                status="unsupported",
                verdict="not_found",
            ),
            assessment(source, "classification"),
        )
    )
    original_profile = profile_for(source)
    state = state_for(source, profile=original_profile)

    result = await EvidenceValidatorAgent(model=model, config=EvidenceValidatorConfig())(state)

    validated = result["validated_profiles"][0]
    assert validated.product is not None
    assert original_profile.product is not None
    assert validated.product.value == original_profile.product.value
    assert validated.product.sources[0].source_id == source.source_id
    assert validated.technologies == []
    assert ProfileField.TECHNOLOGIES in validated.unknown_fields
    assert len(result["validated_claims"]) == 1
    assert len(result["rejected_claims"]) == 1
    assert result["conflicting_claims"] == []
    assert result["evidence_gaps"] == []
    assert len(result["validated_classifications"]) == 1
    assert state["structured_profiles"][0] == original_profile
    assert result["metrics"]["classifier_duration_ms"] == 1.0


@pytest.mark.asyncio
async def test_uncertain_classification_is_insufficient_without_model_item() -> None:
    source = source_for(uuid4())
    uncertain = StartupClassification(
        startup_id=source.startup_id,
        name="Acme",
        status=ClassificationStatus.UNCERTAIN,
        category=None,
        justification="Insufficient evidence.",
        confidence=ConfidenceLevel.LOW,
    )
    model = FakeChatModel(
        output(
            assessment(source, "product"),
            assessment(source, "technologies[0]"),
        )
    )

    result = await EvidenceValidatorAgent(model=model, config=EvidenceValidatorConfig())(
        state_for(source, classification=uncertain)
    )

    classification_result = result["classification_validations"][0]
    assert classification_result.status is EvidenceStatus.INSUFFICIENT
    assert classification_result.category is None
    prompt_items = json.loads(model.calls[0][1].content)["items"]
    assert {item["claim_key"] for item in prompt_items} == {
        "product",
        "technologies[0]",
    }


@pytest.mark.asyncio
async def test_missing_documents_make_every_item_insufficient_without_model() -> None:
    source = source_for(uuid4())
    model = FakeChatModel("must-not-run")
    state = state_for(source)
    state["selected_sources"] = []

    result = await EvidenceValidatorAgent(model=model, config=EvidenceValidatorConfig())(state)

    assert {item.status for item in result["claim_validations"]} == {EvidenceStatus.INSUFFICIENT}
    assert result["classification_validations"][0].status is EvidenceStatus.INSUFFICIENT
    assert result["validated_profiles"][0].product is None
    assert "validator_no_supported_claims" in result["warnings"]
    assert "evidence_validator_source_gap" in result["warnings"]
    assert model.calls == []


@pytest.mark.asyncio
async def test_validator_repairs_missing_claim_key_once() -> None:
    source = source_for(uuid4())
    invalid = output(assessment(source, "product"))
    valid = output(
        assessment(source, "product"),
        assessment(source, "technologies[0]"),
        assessment(source, "classification"),
    )
    model = SequenceChatModel([invalid, valid])

    result = await EvidenceValidatorAgent(model=model, config=EvidenceValidatorConfig())(
        state_for(source)
    )

    assert len(result["claim_validations"]) == 2
    assert result["errors"] == []
    assert result["metrics"]["evidence_validator_repair_count"] == 1.0
    assert "technologies[0]" in model.calls[1][1].content


@pytest.mark.asyncio
async def test_validator_rejects_fabricated_source() -> None:
    source = source_for(uuid4())
    invalid_source = source_for(source.startup_id)
    invalid = output(
        assessment(invalid_source, "product"),
        assessment(source, "technologies[0]"),
        assessment(source, "classification"),
    )
    model = SequenceChatModel([invalid, invalid])

    result = await EvidenceValidatorAgent(model=model, config=EvidenceValidatorConfig())(
        state_for(source)
    )

    assert result["errors"][0].code == "evidence_validator_invalid_output"
    assert {item.status for item in result["claim_validations"]} == {EvidenceStatus.INSUFFICIENT}
    assert result["validated_profiles"][0].product is None


@pytest.mark.asyncio
async def test_validator_batches_items_and_preserves_exact_coverage() -> None:
    source = source_for(uuid4())
    model = SequenceChatModel(
        [
            output(
                assessment(source, "product"),
                assessment(source, "technologies[0]"),
            ),
            output(assessment(source, "classification")),
        ]
    )

    result = await EvidenceValidatorAgent(
        model=model,
        config=EvidenceValidatorConfig(max_items_per_model_call=2),
    )(state_for(source))

    assert len(model.calls) == 2
    assert len(result["validated_claims"]) == 2
    assert len(result["validated_classifications"]) == 1
    assert result["metrics"]["evidence_validator_model_call_count"] == 2.0


@pytest.mark.asyncio
async def test_validator_preserves_completed_batch_when_next_batch_is_unavailable() -> None:
    source = source_for(uuid4())
    model = SequenceChatModel(
        [
            output(assessment(source, "product")),
            ChatModelError(ChatModelErrorCode.UNAVAILABLE, "private-provider-detail"),
        ]
    )

    result = await EvidenceValidatorAgent(
        model=model,
        config=EvidenceValidatorConfig(max_items_per_model_call=1),
    )(state_for(source))

    assert [item.claim_key for item in result["validated_claims"]] == ["product"]
    assert result["evidence_gaps"][0].claim_key == "technologies[0]"
    assert result["errors"][0].code == "evidence_validator_unavailable"
    assert result["metrics"]["evidence_validator_model_call_count"] == 2.0


@pytest.mark.asyncio
async def test_validator_sanitizes_provider_failure() -> None:
    source = source_for(uuid4())
    model = SequenceChatModel(
        [ChatModelError(ChatModelErrorCode.UNAVAILABLE, "private-provider-detail")]
    )

    result = await EvidenceValidatorAgent(model=model, config=EvidenceValidatorConfig())(
        state_for(source)
    )

    assert result["errors"][0].code == "evidence_validator_unavailable"
    assert "private-provider-detail" not in result["errors"][0].message


@pytest.mark.asyncio
async def test_provider_failure_preserves_only_literal_cited_facts() -> None:
    startup_id = uuid4()
    source = source_for(
        startup_id,
        excerpt=(
            "A Hand Talk usa um modelo proprietário de tradução para Libras e "
            "precisa reduzir a latência de geração do avatar."
        ),
    )
    profile = StructuredStartupProfile(
        startup_id=startup_id,
        name="Hand Talk",
        product=ExtractedFact(
            value="modelo proprietário de tradução para Libras",
            sources=[pointer(source)],
        ),
        technical_needs=[
            ExtractedFact(
                value="reduzir a latência de geração do avatar",
                sources=[pointer(source)],
            )
        ],
        claims=[
            ExtractedFact(
                value="atende todos os idiomas do mundo",
                sources=[pointer(source)],
            )
        ],
        unknown_fields=[
            field
            for field in ProfileField
            if field
            not in {ProfileField.PRODUCT, ProfileField.TECHNICAL_NEEDS, ProfileField.CLAIMS}
        ],
    )
    model = SequenceChatModel(
        [ChatModelError(ChatModelErrorCode.UNAVAILABLE, "private-provider-detail")]
    )

    result = await EvidenceValidatorAgent(model=model, config=EvidenceValidatorConfig())(
        state_for(source, profile=profile)
    )

    validated = result["validated_profiles"][0]
    assert validated.product is not None
    assert [item.value for item in validated.technical_needs] == [
        "reduzir a latência de geração do avatar"
    ]
    assert validated.claims == []
    assert result["validated_classifications"] == []
    assert "evidence_validator_literal_fallback" in result["warnings"]
    assert result["errors"][0].code == "evidence_validator_unavailable"
    assert result["metrics"]["evidence_validator_literal_fallback_supported_count"] == 2.0


@pytest.mark.asyncio
async def test_validator_truncates_context_and_logs_no_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = source_for(uuid4(), excerpt="S" * 150)
    model = FakeChatModel(
        output(
            assessment(source, "product"),
            assessment(source, "technologies[0]"),
            assessment(source, "classification"),
        )
    )
    config = EvidenceValidatorConfig(max_context_characters=100)

    with caplog.at_level(logging.INFO, logger="app.graph.agents.evidence_validator"):
        result = await EvidenceValidatorAgent(model=model, config=config)(state_for(source))

    assert "evidence_validator_context_truncated" in result["warnings"]
    assert "S" * 100 in model.calls[0][1].content
    assert "S" * 101 not in model.calls[0][1].content
    assert "S" * 20 not in caplog.text
    assert source.source_url not in caplog.text


def test_validator_factory_uses_fast_model() -> None:
    fast = FakeChatModel()
    heavy = FakeChatModel()

    agent = create_evidence_validator_agent(
        registry=ModelRegistry(llm_fast=fast, llm_heavy=heavy),
        config=EvidenceValidatorConfig(),
    )

    assert agent._model is fast
