from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.api.status import response_status
from app.application.contracts.query_plan import QueryPlan
from app.core.resources import ApplicationResources
from app.domain.models import RecoverableError
from app.graph.state import AppState

router = APIRouter(prefix="/api/v1/query-plans", tags=["query-plans"])


class QueryPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str


class RecoverableErrorResponse(BaseModel):
    code: str
    message: str
    node: str | None = None

    @classmethod
    def from_domain(cls, error: RecoverableError) -> RecoverableErrorResponse:
        return cls(code=error.code, message=error.message, node=error.node)


class QueryPlanResponse(BaseModel):
    query_plan: QueryPlan | None = None
    warnings: list[str]
    errors: list[RecoverableErrorResponse]
    metrics: dict[str, float]


@router.post(
    "",
    response_model=QueryPlanResponse,
    responses={
        422: {"model": QueryPlanResponse},
        502: {"model": QueryPlanResponse},
        503: {"model": QueryPlanResponse},
    },
)
async def create_query_plan(payload: QueryPlanRequest, request: Request) -> JSONResponse:
    resources = cast(ApplicationResources, request.app.state.resources)
    update = await resources.query_planner(AppState(query=payload.query))
    errors = [RecoverableErrorResponse.from_domain(error) for error in update.get("errors", [])]
    response = QueryPlanResponse(
        query_plan=update.get("query_plan"),
        warnings=update.get("warnings", []),
        errors=errors,
        metrics=update.get("metrics", {}),
    )
    return JSONResponse(
        status_code=response_status(update.get("errors", [])),
        content=response.model_dump(mode="json"),
    )
