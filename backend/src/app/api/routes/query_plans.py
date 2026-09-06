from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.application.contracts.query_plan import QueryPlan
from app.core.config import Settings
from app.core.resources import ApplicationResources
from app.domain.models import RecoverableError
from app.graph.agents.query_planner import create_query_planner_agent
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


ERROR_STATUS_BY_CODE = {
    "query_empty": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "query_too_long": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "query_plan_invalid_output": status.HTTP_502_BAD_GATEWAY,
    "query_planner_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


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
    settings = cast(Settings, request.app.state.settings)
    agent = create_query_planner_agent(
        registry=resources.model_registry,
        config=settings.query_planner,
    )
    update = await agent(AppState(query=payload.query))
    errors = [RecoverableErrorResponse.from_domain(error) for error in update.get("errors", [])]
    response = QueryPlanResponse(
        query_plan=update.get("query_plan"),
        warnings=update.get("warnings", []),
        errors=errors,
        metrics=update.get("metrics", {}),
    )
    return JSONResponse(
        status_code=_response_status(errors),
        content=response.model_dump(mode="json"),
    )


def _response_status(errors: list[RecoverableErrorResponse]) -> int:
    for error in errors:
        mapped_status = ERROR_STATUS_BY_CODE.get(error.code)
        if mapped_status is not None:
            return mapped_status
    return status.HTTP_200_OK
