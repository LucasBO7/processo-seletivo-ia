from __future__ import annotations

import json
from itertools import product
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.application.contracts.classification import (
    ClassificationSignal,
    ClassificationSignalType,
    ClassificationStatus,
    ConfidenceLevel,
)
from app.application.contracts.evidence_validation import (
    ValidatedClassification,
    ValidatedStartupProfile,
)
from app.application.contracts.extraction import ExtractedFact, ExtractionSource, ProfileField
from app.application.contracts.knowledge_ingestion import NvidiaTechnology
from app.application.contracts.nvidia_rag import (
    NvidiaContextStatus,
    NvidiaContextSufficiency,
    NvidiaQueryTrace,
    NvidiaRankingMode,
    NvidiaRetrievalScores,
    NvidiaRetrievedChunk,
    NvidiaStartupContext,
)
from app.application.contracts.recommendation import (
    BusinessRelevance,
    EvidenceStrength,
    ImplementationComplexity,
    InfrastructureChange,
    IntegrationScope,
    NeedCriticality,
    RecommendationPriority,
    SpecializedSkills,
    StartupRecommendation,
)
from app.core.config import RecommendationConfig
from app.domain.models import AIMaturity, TechnicalGap
from app.graph.agents.recommendation import (
    RecommendationAgent,
    calculate_complexity,
    calculate_priority,
)
from app.graph.state import AppState
from tests.fakes.providers import FakeChatModel, SequenceChatModel


def profile_fixture(*, with_need: bool = True) -> tuple[ValidatedStartupProfile, list[UUID]]:
    startup_id = uuid4()
    source_ids = [uuid4(), uuid4()]
    sources = [
        ExtractionSource(
            startup_id=startup_id,
            source_id=source_id,
            source_url=f"https://startup.example/{index}",
        )
        for index, source_id in enumerate(source_ids)
    ]
    return (
        ValidatedStartupProfile(
            startup_id=startup_id,
            name="Vision Health",
            product=ExtractedFact(
                value="Core product depends on real-time medical inference",
                sources=[sources[0]],
            ),
            technical_needs=(
                [
                    ExtractedFact(
                        value="Required blocker: inference API has high latency",
                        sources=sources,
                    )
                ]
                if with_need
                else []
            ),
            unknown_fields=[
                field
                for field in ProfileField
                if field not in {ProfileField.PRODUCT, ProfileField.TECHNICAL_NEEDS}
                or (field is ProfileField.TECHNICAL_NEEDS and not with_need)
            ],
        ),
        source_ids,
    )


def context_fixture(
    profile: ValidatedStartupProfile, *, sufficient: bool = True
) -> NvidiaStartupContext:
    chunk = NvidiaRetrievedChunk(
        startup_id=profile.startup_id,
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="NVIDIA NIM provides managed API microservices for model inference.",
        title="NVIDIA NIM",
        technology=NvidiaTechnology.NVIDIA_NIM,
        source_key="nim",
        source_url="https://www.nvidia.com/nim",
        chunk_index=0,
        source_section="API",
        start_offset=0,
        end_offset=65,
        retrieval_attempts=[1],
        matched_queries=["inference"],
        scores=NvidiaRetrievalScores(
            vector_raw_score=0.9,
            vector_rank=1,
            vector_rank_score=1,
            vector_weight=0.5,
            lexical_weight=0.5,
            hybrid_score=0.9,
        ),
    )
    reasons = [] if sufficient else ["minimum_relevant_chunks_not_met"]
    return NvidiaStartupContext(
        startup_id=profile.startup_id,
        startup_name=profile.name,
        attempted_queries=["inference"],
        query_traces=[NvidiaQueryTrace(attempt=1, text="inference")],
        attempts=1,
        chunks=[chunk],
        sufficiency=NvidiaContextSufficiency(
            status=(
                NvidiaContextStatus.SUFFICIENT if sufficient else NvidiaContextStatus.INSUFFICIENT
            ),
            relevant_chunk_count=1,
            distinct_document_count=1,
            best_score=0.9,
            threshold=0.2,
            ranking_mode=NvidiaRankingMode.HYBRID_FALLBACK,
            reasons=reasons,
        ),
        gaps=(
            []
            if sufficient
            else [
                {
                    "code": "nvidia_context_insufficient",
                    "message": "Not enough context.",
                }
            ]
        ),
    )


def candidate_json(source_ids: list[UUID], chunk_id: UUID, **updates: object) -> str:
    candidate: dict[str, object] = {
        "technology": "nvidia_nim",
        "need_keys": ["need:1"],
        "technical_justification": "The documented inference API addresses the latency need.",
        "business_justification": "This supports the startup's core medical product.",
        "next_action": "NVIDIA team should run a technical discovery and proof of concept.",
        "startup_evidence_ids": [str(item) for item in source_ids],
        "nvidia_chunk_ids": [str(chunk_id)],
        "need_criticality": "blocker",
        "business_relevance": "core",
        "priority": "high",
        "priority_evidence_ids": [str(item) for item in source_ids],
        "integration_scope": "configuration_or_api",
        "infrastructure_change": "none",
        "specialized_skills": "standard",
        "implementation_complexity": "low",
        "complexity_nvidia_chunk_ids": [str(chunk_id)],
    }
    candidate.update(updates)
    return json.dumps({"candidates": [candidate]}, separators=(",", ":"))


@pytest.mark.parametrize(
    ("criticality", "relevance", "strength"),
    list(product(NeedCriticality, BusinessRelevance, EvidenceStrength)),
)
def test_priority_table_is_complete_and_deterministic(
    criticality: NeedCriticality,
    relevance: BusinessRelevance,
    strength: EvidenceStrength,
) -> None:
    score, priority = calculate_priority(criticality, relevance, strength)
    expected = (
        {NeedCriticality.OPTIMIZATION: 0, NeedCriticality.IMPORTANT: 1, NeedCriticality.BLOCKER: 2}[
            criticality
        ]
        + (relevance is BusinessRelevance.CORE)
        + (strength is EvidenceStrength.CORROBORATED)
    )
    assert score == expected
    assert priority is (
        RecommendationPriority.LOW
        if score == 0
        else RecommendationPriority.MEDIUM
        if score <= 2
        else RecommendationPriority.HIGH
    )


@pytest.mark.parametrize(
    ("scope", "infrastructure", "skills"),
    list(product(IntegrationScope, InfrastructureChange, SpecializedSkills)),
)
def test_complexity_table_is_complete_and_deterministic(
    scope: IntegrationScope,
    infrastructure: InfrastructureChange,
    skills: SpecializedSkills,
) -> None:
    score, complexity = calculate_complexity(scope, infrastructure, skills)
    assert 0 <= score <= 6
    assert complexity is (
        ImplementationComplexity.LOW
        if score <= 1
        else ImplementationComplexity.MEDIUM
        if score <= 3
        else ImplementationComplexity.HIGH
    )


@pytest.mark.asyncio
async def test_agent_builds_grounded_recommendation_and_derives_fields() -> None:
    profile, source_ids = profile_fixture()
    context = context_fixture(profile)
    model = FakeChatModel(candidate_json(source_ids, context.chunks[0].chunk_id))
    agent = RecommendationAgent(model=model, config=RecommendationConfig())

    patch = await agent(AppState(validated_profiles=[profile], nvidia_contexts=[context]))

    recommendation = patch["recommendations"][0]
    assert recommendation.startup_id == profile.startup_id
    assert recommendation.priority is RecommendationPriority.HIGH
    assert recommendation.priority_basis.priority_score == 4
    assert recommendation.implementation_complexity is ImplementationComplexity.LOW
    assert recommendation.complexity_basis.complexity_score == 0
    assert {item.source_id for item in recommendation.startup_evidence} == set(source_ids)
    assert recommendation.nvidia_evidence[0].source_url == context.chunks[0].source_url
    assert len(model.calls) == 1
    assert patch["metrics"]["recommendation_accepted_count"] == 1
    assert "recommendation_classification_unavailable" in patch["warnings"]


@pytest.mark.asyncio
async def test_agent_skips_missing_need_and_insufficient_context_without_model() -> None:
    no_need, _ = profile_fixture(with_need=False)
    insufficient_profile, _ = profile_fixture()
    model = FakeChatModel("must not be used")
    agent = RecommendationAgent(model=model, config=RecommendationConfig())

    patch = await agent(
        AppState(
            validated_profiles=[no_need, insufficient_profile],
            nvidia_contexts=[
                context_fixture(no_need),
                context_fixture(insufficient_profile, sufficient=False),
            ],
        )
    )

    assert patch["recommendations"] == []
    assert model.calls == []
    assert "recommendation_no_identified_need" in patch["warnings"]
    assert "recommendation_nvidia_context_insufficient" in patch["warnings"]


@pytest.mark.asyncio
async def test_fabricated_chunk_repairs_once_and_publishes_only_valid_batch() -> None:
    profile, source_ids = profile_fixture()
    context = context_fixture(profile)
    valid = candidate_json(source_ids, context.chunks[0].chunk_id)
    invalid = candidate_json(source_ids, uuid4())
    model = SequenceChatModel([invalid, valid])
    agent = RecommendationAgent(model=model, config=RecommendationConfig())

    patch = await agent(AppState(validated_profiles=[profile], nvidia_contexts=[context]))

    assert len(patch["recommendations"]) == 1
    assert len(model.calls) == 2
    assert patch["metrics"]["recommendation_repair_count"] == 1
    repair_prompt = model.calls[1][1].content
    assert str(context.chunks[0].chunk_id) in repair_prompt
    assert "recommendation_nvidia_chunk_not_allowed" in repair_prompt


@pytest.mark.asyncio
async def test_persistent_duplicate_batch_is_atomic_and_sanitized() -> None:
    profile, source_ids = profile_fixture()
    context = context_fixture(profile)
    raw = json.loads(candidate_json(source_ids, context.chunks[0].chunk_id))
    raw["candidates"].append(raw["candidates"][0])
    invalid = json.dumps(raw, separators=(",", ":"))
    model = SequenceChatModel([invalid, invalid])
    agent = RecommendationAgent(model=model, config=RecommendationConfig())

    patch = await agent(AppState(validated_profiles=[profile], nvidia_contexts=[context]))

    assert patch["recommendations"] == []
    assert patch["errors"][0].code == "recommendation_invalid_output"
    assert "Vision Health" not in patch["errors"][0].message
    assert patch["metrics"]["recommendation_invalid_batch_count"] == 1


@pytest.mark.asyncio
async def test_empty_match_and_provider_failure_have_distinct_outcomes() -> None:
    profile, _ = profile_fixture()
    context = context_fixture(profile)
    empty_model = FakeChatModel('{"candidates":[]}')
    empty_patch = await RecommendationAgent(model=empty_model, config=RecommendationConfig())(
        AppState(validated_profiles=[profile], nvidia_contexts=[context])
    )

    assert empty_patch["errors"] == []
    assert "recommendation_no_compatible_match" in empty_patch["warnings"]

    failing_model = SequenceChatModel([RuntimeError("secret provider response")])
    failed_patch = await RecommendationAgent(model=failing_model, config=RecommendationConfig())(
        AppState(validated_profiles=[profile], nvidia_contexts=[context])
    )
    assert failed_patch["errors"][0].code == "recommendation_unavailable"
    assert "secret provider response" not in failed_patch["errors"][0].message


@pytest.mark.asyncio
async def test_context_is_truncated_to_configured_character_limit() -> None:
    profile, source_ids = profile_fixture()
    context = context_fixture(profile)
    context = context.model_copy(
        update={
            "chunks": [context.chunks[0].model_copy(update={"content": "API microservice " * 500})]
        }
    )
    model = FakeChatModel(candidate_json(source_ids, context.chunks[0].chunk_id))
    agent = RecommendationAgent(
        model=model,
        config=RecommendationConfig(max_context_characters=1_000),
    )

    patch = await agent(AppState(validated_profiles=[profile], nvidia_contexts=[context]))

    assert "recommendation_context_truncated" in patch["warnings"]
    assert len(model.calls[0][1].content) <= 1_000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("maturity", "signal_type", "has_match"),
    [
        (AIMaturity.AI_NATIVE, ClassificationSignalType.CORE_AI_DEPENDENCY, True),
        (AIMaturity.AI_ENABLED, ClassificationSignalType.SUPPORTING_AI_USE, True),
        (AIMaturity.NON_AI, ClassificationSignalType.EXPLICIT_NON_AI, False),
    ],
)
async def test_representative_maturity_scenarios(
    maturity: AIMaturity,
    signal_type: ClassificationSignalType,
    has_match: bool,
) -> None:
    profile, source_ids = profile_fixture()
    context = context_fixture(profile)
    assert profile.product is not None
    source = profile.product.sources[0]
    classification = ValidatedClassification(
        startup_id=profile.startup_id,
        name=profile.name,
        status=ClassificationStatus.CLASSIFIED,
        category=maturity,
        justification="Validated classification.",
        confidence=ConfidenceLevel.MEDIUM,
        signals=[
            ClassificationSignal(
                type=signal_type,
                description="Documented AI relationship.",
                sources=[source],
            )
        ],
        evidence_references=[source],
    )
    response = (
        candidate_json(source_ids, context.chunks[0].chunk_id) if has_match else '{"candidates":[]}'
    )
    patch = await RecommendationAgent(model=FakeChatModel(response), config=RecommendationConfig())(
        AppState(
            validated_profiles=[profile],
            validated_classifications=[classification],
            nvidia_contexts=[context],
        )
    )

    if has_match:
        assert patch["recommendations"][0].maturity_considered is maturity
    else:
        assert patch["recommendations"] == []
        assert "recommendation_no_compatible_match" in patch["warnings"]


@pytest.mark.asyncio
async def test_untraceable_gap_is_warned_and_excluded_from_prompt() -> None:
    profile, source_ids = profile_fixture()
    context = context_fixture(profile)
    model = FakeChatModel(candidate_json(source_ids, context.chunks[0].chunk_id))
    patch = await RecommendationAgent(model=model, config=RecommendationConfig())(
        AppState(
            validated_profiles=[profile],
            nvidia_contexts=[context],
            technical_gaps=[
                TechnicalGap(
                    name="Untrusted",
                    description="SECRET UNTRACEABLE GAP",
                    evidence_ids=(uuid4(),),
                )
            ],
        )
    )

    assert "recommendation_gap_untraceable" in patch["warnings"]
    assert "SECRET UNTRACEABLE GAP" not in model.calls[0][1].content


@pytest.mark.asyncio
async def test_technology_mismatch_is_rejected_without_partial_publication() -> None:
    profile, source_ids = profile_fixture()
    context = context_fixture(profile)
    invalid = candidate_json(
        source_ids,
        context.chunks[0].chunk_id,
        technology="tensorrt_llm",
    )
    patch = await RecommendationAgent(
        model=FakeChatModel(invalid),
        config=RecommendationConfig(max_repair_attempts=0),
    )(AppState(validated_profiles=[profile], nvidia_contexts=[context]))

    assert patch["recommendations"] == []
    assert patch["errors"][0].code == "recommendation_invalid_output"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "update",
    [
        {"priority": "medium"},
        {"implementation_complexity": "medium"},
    ],
)
async def test_derived_priority_and_complexity_must_match_model_proposal(
    update: dict[str, object],
) -> None:
    profile, source_ids = profile_fixture()
    context = context_fixture(profile)
    invalid = candidate_json(source_ids, context.chunks[0].chunk_id, **update)
    patch = await RecommendationAgent(
        model=FakeChatModel(invalid),
        config=RecommendationConfig(max_repair_attempts=0),
    )(AppState(validated_profiles=[profile], nvidia_contexts=[context]))

    assert patch["recommendations"] == []
    assert patch["errors"][0].code == "recommendation_invalid_output"


@pytest.mark.asyncio
async def test_startups_are_isolated_and_previous_valid_batch_survives_failure() -> None:
    first_profile, first_sources = profile_fixture()
    second_profile, _ = profile_fixture()
    first_context = context_fixture(first_profile)
    second_context = context_fixture(second_profile)
    model = SequenceChatModel(
        [
            candidate_json(first_sources, first_context.chunks[0].chunk_id),
            RuntimeError("provider failed"),
        ]
    )
    patch = await RecommendationAgent(model=model, config=RecommendationConfig())(
        AppState(
            validated_profiles=[first_profile, second_profile],
            nvidia_contexts=[first_context, second_context],
        )
    )

    assert [item.startup_id for item in patch["recommendations"]] == [first_profile.startup_id]
    assert patch["errors"][0].code == "recommendation_unavailable"
    assert str(second_context.chunks[0].chunk_id) not in model.calls[0][1].content
    assert str(first_context.chunks[0].chunk_id) not in model.calls[1][1].content


@pytest.mark.asyncio
async def test_explicit_profile_constraint_rejects_incompatible_technology() -> None:
    profile, source_ids = profile_fixture()
    assert profile.product is not None
    restricted = profile.model_copy(
        update={
            "external_dependencies": [
                ExtractedFact(
                    value="The current environment is incompatible with NVIDIA NIM.",
                    sources=profile.product.sources,
                )
            ],
            "unknown_fields": [
                field
                for field in profile.unknown_fields
                if field is not ProfileField.EXTERNAL_DEPENDENCIES
            ],
        }
    )
    context = context_fixture(restricted)
    raw = candidate_json(source_ids, context.chunks[0].chunk_id)
    patch = await RecommendationAgent(
        model=FakeChatModel(raw),
        config=RecommendationConfig(max_repair_attempts=0),
    )(AppState(validated_profiles=[restricted], nvidia_contexts=[context]))

    assert patch["recommendations"] == []
    assert patch["errors"][0].code == "recommendation_invalid_output"


def test_final_contract_is_strict_and_immutable() -> None:
    with pytest.raises(ValidationError):
        StartupRecommendation.model_validate({"unexpected": True})
