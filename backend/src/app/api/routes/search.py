from __future__ import annotations

import logging
from enum import StrEnum
from math import isfinite
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.routes.query_plans import RecoverableErrorResponse
from app.api.status import response_status
from app.application.contracts.briefing import StartupBriefing
from app.application.contracts.classification import StartupClassification
from app.application.contracts.evidence_validation import (
    ClaimValidation,
    ClassificationValidation,
    ValidatedClassification,
    ValidatedStartupProfile,
)
from app.application.contracts.extraction import StructuredStartupProfile
from app.application.contracts.nvidia_rag import NvidiaStartupContext
from app.application.contracts.query_plan import QueryPlan, QueryPlanStatus
from app.application.contracts.recommendation import StartupRecommendation
from app.core.resources import ApplicationResources
from app.domain.models import RecoverableError
from app.graph.state import AppState, empty_state

router = APIRouter(prefix="/api/v1/search", tags=["search"])
logger = logging.getLogger("app.analysis")

PUBLIC_METRIC_PREFIXES = (
    "query_planner_",
    "retriever_",
    "extractor_",
    "classifier_",
    "evidence_validator_",
    "nvidia_rag_",
    "recommendation_",
    "briefing_",
)


class AnalysisOutcome(StrEnum):
    SUCCESS = "success"
    NEEDS_CLARIFICATION = "needs_clarification"
    INVALID_QUERY = "invalid_query"
    NO_RESULTS = "no_results"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    INTERNAL_FAILURE = "internal_failure"


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(examples=["startups brasileiras de saúde usando IA"])


class CandidateStartupResponse(BaseModel):
    startup_id: UUID
    name: str
    score: float | None


class SourceReferenceResponse(BaseModel):
    startup_id: UUID
    source_id: UUID
    source_url: str
    title: str
    excerpt: str | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: AnalysisOutcome
    query_plan: QueryPlan | None = None
    candidate_startups: list[CandidateStartupResponse]
    selected_sources: list[SourceReferenceResponse]
    structured_profiles: list[StructuredStartupProfile]
    classifications: list[StartupClassification]
    validated_profiles: list[ValidatedStartupProfile]
    validated_classifications: list[ValidatedClassification]
    claim_validations: list[ClaimValidation]
    classification_validations: list[ClassificationValidation]
    validated_claims: list[ClaimValidation]
    rejected_claims: list[ClaimValidation]
    conflicting_claims: list[ClaimValidation]
    evidence_gaps: list[ClaimValidation]
    nvidia_contexts: list[NvidiaStartupContext]
    recommendations: list[StartupRecommendation]
    briefings: list[StartupBriefing]
    warnings: list[str]
    errors: list[RecoverableErrorResponse]
    metrics: dict[str, float]


def public_metrics(metrics: dict[str, float]) -> dict[str, float]:
    return {
        key: value
        for key, value in metrics.items()
        if key.startswith(PUBLIC_METRIC_PREFIXES) and isfinite(value)
    }


def analysis_outcome(state: AppState, status_code: int) -> AnalysisOutcome:
    if status_code == 503:
        return AnalysisOutcome.TEMPORARILY_UNAVAILABLE
    if status_code >= 500:
        return AnalysisOutcome.INTERNAL_FAILURE

    plan = state.get("query_plan")
    if isinstance(plan, QueryPlan):
        if plan.status is QueryPlanStatus.NEEDS_CLARIFICATION:
            return AnalysisOutcome.NEEDS_CLARIFICATION
        if plan.status is QueryPlanStatus.INVALID:
            return AnalysisOutcome.INVALID_QUERY

    if status_code == 422:
        return AnalysisOutcome.INVALID_QUERY
    if not state.get("candidate_startups"):
        return AnalysisOutcome.NO_RESULTS
    return AnalysisOutcome.SUCCESS


def build_search_response(state: AppState, *, status_code: int) -> SearchResponse:
    errors = state.get("errors", [])
    return SearchResponse(
        outcome=analysis_outcome(state, status_code),
        query_plan=state.get("query_plan"),
        candidate_startups=[
            CandidateStartupResponse.model_validate(candidate)
            for candidate in state.get("candidate_startups", [])
        ],
        selected_sources=[
            SourceReferenceResponse(
                startup_id=source.startup_id,
                source_id=source.source_id,
                source_url=source.source_url,
                title=source.title,
                excerpt=source.excerpt,
            )
            for source in state.get("selected_sources", [])
        ],
        structured_profiles=state.get("structured_profiles", []),
        classifications=state.get("classifications", []),
        validated_profiles=state.get("validated_profiles", []),
        validated_classifications=state.get("validated_classifications", []),
        claim_validations=state.get("claim_validations", []),
        classification_validations=state.get("classification_validations", []),
        validated_claims=state.get("validated_claims", []),
        rejected_claims=state.get("rejected_claims", []),
        conflicting_claims=state.get("conflicting_claims", []),
        evidence_gaps=state.get("evidence_gaps", []),
        nvidia_contexts=state.get("nvidia_contexts", []),
        recommendations=state.get("recommendations", []),
        briefings=state.get("briefings", []),
        warnings=state.get("warnings", []),
        errors=[RecoverableErrorResponse.from_domain(error) for error in errors],
        metrics=public_metrics(state.get("metrics", {})),
    )


EMPTY_ANALYSIS_EXAMPLE: dict[str, object] = {
    "query_plan": None,
    "candidate_startups": [],
    "selected_sources": [],
    "structured_profiles": [],
    "classifications": [],
    "validated_profiles": [],
    "validated_classifications": [],
    "claim_validations": [],
    "classification_validations": [],
    "validated_claims": [],
    "rejected_claims": [],
    "conflicting_claims": [],
    "evidence_gaps": [],
    "nvidia_contexts": [],
    "recommendations": [],
    "briefings": [],
    "warnings": [],
    "errors": [],
    "metrics": {},
}


def _response_example(outcome: AnalysisOutcome, **updates: object) -> dict[str, object]:
    return {"outcome": outcome.value, **EMPTY_ANALYSIS_EXAMPLE, **updates}


ANALYSIS_EXAMPLES = {
    "success": {
        "summary": "Análise concluída",
        "value": _response_example(
            AnalysisOutcome.SUCCESS,
            candidate_startups=[
                {
                    "startup_id": "9af21404-d8e7-46f4-b57c-669fc965699b",
                    "name": "Startup Exemplo",
                    "score": 0.91,
                }
            ],
            warnings=[],
            metrics={"briefing_duration_ms": 12.4},
        ),
    },
    "needs_clarification": {
        "summary": "Consulta precisa de esclarecimento",
        "value": _response_example(
            AnalysisOutcome.NEEDS_CLARIFICATION,
            warnings=["query_plan_needs_clarification"],
        ),
    },
    "no_results": {
        "summary": "Nenhuma startup encontrada",
        "value": _response_example(
            AnalysisOutcome.NO_RESULTS,
            warnings=["retriever_no_results"],
        ),
    },
    "invalid_query": {
        "summary": "Consulta inválida",
        "value": _response_example(
            AnalysisOutcome.INVALID_QUERY,
            errors=[
                {
                    "code": "query_invalid",
                    "message": "Consulta fora do escopo.",
                    "node": "query_planner",
                }
            ],
        ),
    },
    "temporarily_unavailable": {
        "summary": "Dependência temporariamente indisponível",
        "value": _response_example(
            AnalysisOutcome.TEMPORARILY_UNAVAILABLE,
            errors=[
                {
                    "code": "retriever_unavailable",
                    "message": "A recuperação está temporariamente indisponível.",
                    "node": "retriever",
                }
            ],
        ),
    },
    "internal_failure": {
        "summary": "Falha interna sanitizada",
        "value": _response_example(
            AnalysisOutcome.INTERNAL_FAILURE,
            errors=[
                {
                    "code": "analysis_internal_error",
                    "message": "A análise não pôde ser concluída.",
                    "node": None,
                }
            ],
        ),
    },
}


@router.post(
    "",
    response_model=SearchResponse,
    responses={
        200: {
            "description": "Sucesso, esclarecimento necessário ou ausência de resultados.",
            "content": {
                "application/json": {
                    "examples": {
                        key: ANALYSIS_EXAMPLES[key]
                        for key in ("success", "needs_clarification", "no_results")
                    }
                }
            },
        },
        422: {
            "model": SearchResponse,
            "content": {
                "application/json": {
                    "examples": {"invalid_query": ANALYSIS_EXAMPLES["invalid_query"]}
                }
            },
        },
        502: {
            "model": SearchResponse,
            "content": {
                "application/json": {
                    "examples": {"internal_failure": ANALYSIS_EXAMPLES["internal_failure"]}
                }
            },
        },
        503: {
            "model": SearchResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "temporarily_unavailable": ANALYSIS_EXAMPLES["temporarily_unavailable"]
                    }
                }
            },
        },
        500: {
            "model": SearchResponse,
            "content": {
                "application/json": {
                    "examples": {"internal_failure": ANALYSIS_EXAMPLES["internal_failure"]}
                }
            },
        },
    },
)
async def search(payload: SearchRequest, request: Request) -> JSONResponse:
    resources = cast(ApplicationResources, request.app.state.resources)
    correlation_id = cast(str, request.state.correlation_id)
    try:
        final_state = await resources.workflow.ainvoke(
            empty_state(run_id=uuid4(), correlation_id=correlation_id, query=payload.query)
        )
    except Exception:
        logger.error("analysis_failed", extra={"correlation_id": correlation_id})
        final_state = AppState(
            errors=[
                RecoverableError(
                    code="analysis_internal_error",
                    message="A análise não pôde ser concluída.",
                )
            ]
        )
        response = build_search_response(final_state, status_code=500)
        return JSONResponse(status_code=500, content=response.model_dump(mode="json"))

    errors = final_state.get("errors", [])
    status_code = response_status(errors)
    plan = final_state.get("query_plan")
    if isinstance(plan, QueryPlan) and plan.status is QueryPlanStatus.INVALID:
        status_code = 422
    response = build_search_response(final_state, status_code=status_code)
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json"),
    )
