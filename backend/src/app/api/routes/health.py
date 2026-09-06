from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.resources import ApplicationResources

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["alive"] = "alive"


class DependencyStatus(BaseModel):
    postgres: bool
    qdrant: bool


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: DependencyStatus


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readiness(request: Request) -> ReadinessResponse | JSONResponse:
    resources: ApplicationResources = request.app.state.resources
    postgres_ready = await resources.postgres_probe.check()
    qdrant_ready = await resources.qdrant_probe.check()
    dependencies = DependencyStatus(postgres=postgres_ready, qdrant=qdrant_ready)
    if postgres_ready and qdrant_ready:
        return ReadinessResponse(status="ready", dependencies=dependencies)
    body = ReadinessResponse(status="not_ready", dependencies=dependencies)
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body.model_dump())
