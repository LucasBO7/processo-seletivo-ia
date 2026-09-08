from __future__ import annotations

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.application.contracts.briefing import BriefingMissingSection, StartupBriefing
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
    ComplexityBasis,
    EvidenceStrength,
    ImplementationComplexity,
    InfrastructureChange,
    IntegrationScope,
    NeedCriticality,
    NvidiaRecommendationEvidence,
    PriorityBasis,
    RecommendationPriority,
    SpecializedSkills,
    StartupRecommendation,
    StartupRecommendationEvidence,
)
from app.core.config import BriefingConfig
from app.domain.models import AIMaturity, TechnicalGap
from app.graph.agents.briefing import BriefingAgent
from app.graph.state import AppState
from tests.fakes.providers import FakeChatModel, SequenceChatModel


def briefing_inputs() -> tuple[
    ValidatedStartupProfile,
    ValidatedClassification,
    StartupRecommendation,
    NvidiaStartupContext,
    TechnicalGap,
]:
    startup_id = uuid4()
    source_id = uuid4()
    source = ExtractionSource(
        startup_id=startup_id,
        source_id=source_id,
        source_url="https://startup.example/evidence",
    )
    product = ExtractedFact(
        value="Core inference product requires lower latency",
        sources=[source],
    )
    stack = ExtractedFact(value="Python inference API", sources=[source])
    need = ExtractedFact(value="Required inference latency improvement", sources=[source])
    profile = ValidatedStartupProfile(
        startup_id=startup_id,
        name="Vision Health",
        product=product,
        technologies=[stack],
        technical_needs=[need],
        unknown_fields=[
            field
            for field in ProfileField
            if field
            not in {ProfileField.PRODUCT, ProfileField.TECHNOLOGIES, ProfileField.TECHNICAL_NEEDS}
        ],
    )
    classification = ValidatedClassification(
        startup_id=startup_id,
        name=profile.name,
        status=ClassificationStatus.CLASSIFIED,
        category=AIMaturity.AI_NATIVE,
        justification="The core product depends on inference.",
        confidence=ConfidenceLevel.HIGH,
        signals=[
            ClassificationSignal(
                type=ClassificationSignalType.CORE_AI_DEPENDENCY,
                description="Core product depends on inference",
                sources=[source],
            )
        ],
        evidence_references=[source],
    )
    scores = NvidiaRetrievalScores(
        vector_raw_score=0.9,
        vector_rank=1,
        vector_rank_score=1,
        vector_weight=0.5,
        lexical_weight=0.5,
        hybrid_score=0.9,
    )
    nim_chunk = NvidiaRetrievedChunk(
        startup_id=startup_id,
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="NVIDIA NIM provides inference API microservices.",
        title="NVIDIA NIM",
        technology=NvidiaTechnology.NVIDIA_NIM,
        source_key="nim",
        source_url="https://www.nvidia.com/nim",
        chunk_index=0,
        source_section="API",
        start_offset=0,
        end_offset=48,
        retrieval_attempts=[1],
        matched_queries=["inference"],
        scores=scores,
    )
    inception_chunk = NvidiaRetrievedChunk(
        startup_id=startup_id,
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="NVIDIA Inception supports startups with program resources.",
        title="NVIDIA Inception",
        technology=NvidiaTechnology.NVIDIA_INCEPTION,
        source_key="inception",
        source_url="https://www.nvidia.com/startups/",
        chunk_index=0,
        source_section="Program",
        start_offset=0,
        end_offset=58,
        retrieval_attempts=[1],
        matched_queries=["startup program"],
        scores=scores,
    )
    context = NvidiaStartupContext(
        startup_id=startup_id,
        startup_name=profile.name,
        attempted_queries=["inference"],
        query_traces=[NvidiaQueryTrace(attempt=1, text="inference")],
        attempts=1,
        chunks=[nim_chunk, inception_chunk],
        sufficiency=NvidiaContextSufficiency(
            status=NvidiaContextStatus.SUFFICIENT,
            relevant_chunk_count=2,
            distinct_document_count=2,
            best_score=0.9,
            threshold=0.2,
            ranking_mode=NvidiaRankingMode.HYBRID_FALLBACK,
        ),
    )
    recommendation = StartupRecommendation(
        startup_id=startup_id,
        startup_name=profile.name,
        maturity_considered=AIMaturity.AI_NATIVE,
        technology=NvidiaTechnology.NVIDIA_NIM,
        need_keys=["need:1"],
        technical_justification="NVIDIA NIM addresses inference latency.",
        business_justification="Inference supports the core product.",
        priority=RecommendationPriority.HIGH,
        priority_basis=PriorityBasis(
            need_criticality=NeedCriticality.BLOCKER,
            business_relevance=BusinessRelevance.CORE,
            evidence_strength=EvidenceStrength.SINGLE_SOURCE,
            priority_score=3,
            evidence_ids=[source_id],
        ),
        implementation_complexity=ImplementationComplexity.LOW,
        complexity_basis=ComplexityBasis(
            integration_scope=IntegrationScope.CONFIGURATION_OR_API,
            infrastructure_change=InfrastructureChange.NONE,
            specialized_skills=SpecializedSkills.STANDARD,
            complexity_score=0,
            nvidia_chunk_ids=[nim_chunk.chunk_id],
        ),
        next_action="Run an inference technical discovery.",
        startup_evidence=[
            StartupRecommendationEvidence(
                startup_id=startup_id,
                source_id=source_id,
                source_url=source.source_url,
                field=ProfileField.TECHNICAL_NEEDS,
                value=need.value,
            ),
            StartupRecommendationEvidence(
                startup_id=startup_id,
                source_id=source_id,
                source_url=source.source_url,
                field=ProfileField.PRODUCT,
                value=product.value,
            ),
        ],
        nvidia_evidence=[
            NvidiaRecommendationEvidence(
                chunk_id=nim_chunk.chunk_id,
                document_id=nim_chunk.document_id,
                title=nim_chunk.title,
                technology=nim_chunk.technology,
                source_url=nim_chunk.source_url,
                source_section=nim_chunk.source_section,
                start_offset=nim_chunk.start_offset,
                end_offset=nim_chunk.end_offset,
                retrieval_scores=scores,
            )
        ],
    )
    gap = TechnicalGap(
        name="Latency",
        description="Inference latency remains a technical gap",
        evidence_ids=(source_id,),
    )
    return profile, classification, recommendation, context, gap


def narrative_json(**updates: object) -> str:
    payload: dict[str, object] = {
        "executive_summary": [
            {
                "kind": "supported_inference",
                "text": "The inference product can use NVIDIA NIM.",
                "citation_ids": ["S1", "N1"],
            }
        ],
        "inception_opportunities": [
            {
                "kind": "supported_inference",
                "text": "The startup product may explore NVIDIA Inception.",
                "citation_ids": ["S1", "N2"],
            }
        ],
        "uncertainties_and_gaps": [
            {
                "kind": "gap",
                "text": "Inference latency remains a technical gap.",
                "citation_ids": ["S1"],
            }
        ],
    }
    payload.update(updates)
    return json.dumps(payload, separators=(",", ":"))


def full_state() -> AppState:
    profile, classification, recommendation, context, gap = briefing_inputs()
    return AppState(
        validated_profiles=[profile],
        validated_classifications=[classification],
        recommendations=[recommendation],
        nvidia_contexts=[context],
        technical_gaps=[gap],
    )


@pytest.mark.asyncio
async def test_agent_builds_structured_and_markdown_briefing_with_traceable_citations() -> None:
    state = full_state()
    model = FakeChatModel(narrative_json())

    patch = await BriefingAgent(model=model, config=BriefingConfig())(state)

    briefing = patch["briefings"][0]
    assert briefing.ai_maturity is AIMaturity.AI_NATIVE
    assert briefing.business_facts
    assert briefing.classification_signals
    assert briefing.identified_stack
    assert briefing.technical_gaps
    assert briefing.recommendations[0].priority is RecommendationPriority.HIGH
    assert briefing.recommendations[0].implementation_complexity is ImplementationComplexity.LOW
    assert briefing.inception_opportunities[0].citation_ids == ["S1", "N2"]
    assert "## Tecnologias NVIDIA recomendadas" in briefing.markdown
    assert briefing.recommendations[0].priority_citation_ids == ["S1"]
    assert briefing.recommendations[0].complexity_citation_ids == ["N1"]
    assert "Prioridade: high [S1]" in briefing.markdown
    assert "Complexidade: low [N1]" in briefing.markdown
    assert "https://startup.example/evidence" in briefing.markdown
    assert "https://www.nvidia.com/startups/" in briefing.markdown
    assert patch["metrics"]["briefing_accepted_briefing_count"] == 1
    assert patch["metrics"]["briefing_statement_count"] == 3
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_agent_does_not_call_model_without_recommendations() -> None:
    model = FakeChatModel("must not be called")

    patch = await BriefingAgent(model=model, config=BriefingConfig())(AppState())

    assert patch["briefings"] == []
    assert patch["warnings"] == ["briefing_no_recommendations"]
    assert model.calls == []


@pytest.mark.asyncio
async def test_agent_repairs_unknown_citation_once() -> None:
    invalid = narrative_json(
        executive_summary=[
            {
                "kind": "supported_inference",
                "text": "The inference product can use NVIDIA NIM.",
                "citation_ids": ["S1", "N999"],
            }
        ]
    )
    model = SequenceChatModel([invalid, narrative_json()])

    patch = await BriefingAgent(model=model, config=BriefingConfig())(full_state())

    assert len(patch["briefings"]) == 1
    assert patch["metrics"]["briefing_repair_count"] == 1
    assert len(model.calls) == 2
    assert "briefing_citation_not_allowed" in model.calls[1][1].content


@pytest.mark.asyncio
async def test_agent_rejects_invalid_output_and_sanitizes_provider_failure() -> None:
    invalid_model = SequenceChatModel(["{}", "{}"])
    invalid_patch = await BriefingAgent(model=invalid_model, config=BriefingConfig())(full_state())
    failing_model = SequenceChatModel([RuntimeError("secret-token")])
    failing_patch = await BriefingAgent(model=failing_model, config=BriefingConfig())(full_state())

    assert invalid_patch["briefings"] == []
    assert invalid_patch["errors"][0].code == "briefing_invalid_output"
    assert failing_patch["briefings"] == []
    assert failing_patch["errors"][0].code == "briefing_unavailable"
    assert "secret-token" not in failing_patch["errors"][0].message


@pytest.mark.asyncio
async def test_agent_supports_partial_data_and_marks_missing_sections() -> None:
    _, _, recommendation, context, _ = briefing_inputs()
    model = FakeChatModel(narrative_json())

    patch = await BriefingAgent(model=model, config=BriefingConfig())(
        AppState(recommendations=[recommendation], nvidia_contexts=[context])
    )

    briefing = patch["briefings"][0]
    assert briefing.ai_maturity is None
    assert BriefingMissingSection.PROFILE in briefing.missing_sections
    assert BriefingMissingSection.AI_MATURITY in briefing.missing_sections
    assert BriefingMissingSection.SIGNALS in briefing.missing_sections
    assert "briefing_profile_unavailable" in patch["warnings"]
    assert "briefing_classification_unavailable" in patch["warnings"]


@pytest.mark.asyncio
async def test_agent_omits_inception_opportunity_without_official_context() -> None:
    profile, classification, recommendation, context, gap = briefing_inputs()
    context_without_inception = context.model_copy(update={"chunks": context.chunks[:1]})
    model = FakeChatModel(narrative_json(inception_opportunities=[]))

    patch = await BriefingAgent(model=model, config=BriefingConfig())(
        AppState(
            validated_profiles=[profile],
            validated_classifications=[classification],
            recommendations=[recommendation],
            nvidia_contexts=[context_without_inception],
            technical_gaps=[gap],
        )
    )

    briefing = patch["briefings"][0]
    assert briefing.inception_opportunities == []
    assert BriefingMissingSection.INCEPTION_OPPORTUNITIES in briefing.missing_sections
    assert "briefing_inception_context_unavailable" in patch["warnings"]


@pytest.mark.asyncio
async def test_markdown_is_deterministic_escaped_and_bounded() -> None:
    state = full_state()
    recommendation = state["recommendations"][0].model_copy(update={"startup_name": "[Vision]"})
    state["recommendations"] = [recommendation]
    config = BriefingConfig(max_markdown_characters=1_000)

    first = await BriefingAgent(model=FakeChatModel(narrative_json()), config=config)(state)
    second = await BriefingAgent(model=FakeChatModel(narrative_json()), config=config)(state)

    first_markdown = first["briefings"][0].markdown
    assert first_markdown == second["briefings"][0].markdown
    assert "\\[Vision\\]" in first_markdown
    assert len(first_markdown) <= 1_000
    assert "Conteúdo truncado" in first_markdown
    assert "briefing_context_truncated" in first["warnings"]


@pytest.mark.asyncio
async def test_prompt_context_truncation_is_reported() -> None:
    state = full_state()
    profile = state["validated_profiles"][0]
    source = profile.product.sources[0]
    state["validated_profiles"] = [
        profile.model_copy(
            update={
                "product": ExtractedFact(value="inference " * 300, sources=[source]),
            }
        )
    ]

    response = narrative_json(
        executive_summary=[
            {
                "kind": "confirmed_fact",
                "text": "Required inference latency improvement.",
                "citation_ids": ["S1"],
            }
        ],
        inception_opportunities=[],
        uncertainties_and_gaps=[],
    )
    patch = await BriefingAgent(
        model=FakeChatModel(response),
        config=BriefingConfig(max_context_characters=5_000),
    )(state)

    assert len(patch["briefings"]) == 1
    assert "briefing_context_truncated" in patch["warnings"]
    assert patch["metrics"]["briefing_truncation_count"] >= 1


@pytest.mark.asyncio
async def test_failure_for_one_startup_preserves_completed_briefings() -> None:
    first = briefing_inputs()
    second = briefing_inputs()
    model = SequenceChatModel([narrative_json(), RuntimeError("provider secret")])

    patch = await BriefingAgent(model=model, config=BriefingConfig())(
        AppState(
            validated_profiles=[first[0], second[0]],
            validated_classifications=[first[1], second[1]],
            recommendations=[first[2], second[2]],
            nvidia_contexts=[first[3], second[3]],
            technical_gaps=[first[4], second[4]],
        )
    )

    assert [item.startup_id for item in patch["briefings"]] == [first[0].startup_id]
    assert patch["errors"][0].code == "briefing_unavailable"
    assert patch["metrics"]["briefing_failure_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_statement",
    [
        {
            "kind": "confirmed_fact",
            "text": "The inference product can use NVIDIA NIM.",
            "citation_ids": ["S1", "N1"],
        },
        {
            "kind": "supported_inference",
            "text": "The startup product may explore NVIDIA Inception.",
            "citation_ids": ["S1", "N1"],
        },
    ],
)
async def test_agent_rejects_invalid_source_semantics(
    invalid_statement: dict[str, object],
) -> None:
    response = narrative_json(
        executive_summary=[invalid_statement],
        inception_opportunities=(
            [invalid_statement] if invalid_statement["kind"] == "supported_inference" else []
        ),
    )

    patch = await BriefingAgent(
        model=FakeChatModel(response),
        config=BriefingConfig(max_repair_attempts=0),
    )(full_state())

    assert patch["briefings"] == []
    assert patch["errors"][0].code == "briefing_invalid_output"


@pytest.mark.asyncio
async def test_structured_contract_rejects_maturity_without_citations() -> None:
    patch = await BriefingAgent(model=FakeChatModel(narrative_json()), config=BriefingConfig())(
        full_state()
    )
    payload = patch["briefings"][0].model_dump()
    payload["ai_maturity_citation_ids"] = []

    with pytest.raises(ValidationError, match="AI maturity requires citations"):
        StartupBriefing.model_validate(payload)
