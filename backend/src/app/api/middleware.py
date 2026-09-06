from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

logger = logging.getLogger("app.http")

CORRELATION_HEADER = "X-Correlation-ID"


async def correlation_and_logging_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid4())
    request.state.correlation_id = correlation_id
    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    response.headers[CORRELATION_HEADER] = correlation_id
    logger.info(
        "request_completed",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "route": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
