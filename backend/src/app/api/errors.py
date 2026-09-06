from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    correlation_id: str
