from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.api.routes.query_plans import RecoverableErrorResponse
from app.api.status import response_status
from app.application.contracts.classification import StartupClassification
from app.application.contracts.evidence_validation import (
    ClaimValidation,
    ClassificationValidation,
    ValidatedClassification,
    ValidatedStartupProfile,
)
from app.application.contracts.extraction import StructuredStartupProfile
from app.application.contracts.query_plan import QueryPlan
from app.core.resources import ApplicationResources
from app.graph.state import empty_state

router = APIRouter(prefix="/api/v1/search", tags=["search"])


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str


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
    warnings: list[str]
    errors: list[RecoverableErrorResponse]
    metrics: dict[str, float]


@router.post(
    "",
    response_model=SearchResponse,
    responses={
        422: {"model": SearchResponse},
        502: {"model": SearchResponse},
        503: {"model": SearchResponse},
    },
)
async def search(payload: SearchRequest, request: Request) -> JSONResponse:
    resources = cast(ApplicationResources, request.app.state.resources)
    correlation_id = cast(str, request.state.correlation_id)
    final_state = await resources.workflow.ainvoke(
        empty_state(run_id=uuid4(), correlation_id=correlation_id, query=payload.query)
    )
    errors = final_state.get("errors", [])
    response = SearchResponse(
        query_plan=final_state.get("query_plan"),
        candidate_startups=[
            CandidateStartupResponse.model_validate(candidate)
            for candidate in final_state.get("candidate_startups", [])
        ],
        selected_sources=[
            SourceReferenceResponse(
                startup_id=source.startup_id,
                source_id=source.source_id,
                source_url=source.source_url,
                title=source.title,
                excerpt=source.excerpt,
            )
            for source in final_state.get("selected_sources", [])
        ],
        structured_profiles=final_state.get("structured_profiles", []),
        classifications=final_state.get("classifications", []),
        validated_profiles=final_state.get("validated_profiles", []),
        validated_classifications=final_state.get("validated_classifications", []),
        claim_validations=final_state.get("claim_validations", []),
        classification_validations=final_state.get("classification_validations", []),
        validated_claims=final_state.get("validated_claims", []),
        rejected_claims=final_state.get("rejected_claims", []),
        conflicting_claims=final_state.get("conflicting_claims", []),
        evidence_gaps=final_state.get("evidence_gaps", []),
        warnings=final_state.get("warnings", []),
        errors=[RecoverableErrorResponse.from_domain(error) for error in errors],
        metrics=final_state.get("metrics", {}),
    )
    return JSONResponse(
        status_code=response_status(errors),
        content=response.model_dump(mode="json"),
    )
