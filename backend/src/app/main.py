from __future__ import annotations

import asyncio
import selectors
import sys

import uvicorn

from app.api.app import create_app
from app.core.config import get_settings


def event_loop_factory() -> asyncio.AbstractEventLoop:
    """Build an event loop compatible with psycopg async on every platform."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.new_event_loop()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.http.host,
        port=settings.http.port,
        reload=settings.app.environment == "local",
        log_config=None,
        loop="app.main:event_loop_factory",
    )


app = create_app()


if __name__ == "__main__":
    run()
