from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.config import Settings
from app.core.resources import ApplicationResources

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class StubProbe:
    def __init__(self, ready: bool = True) -> None:
        self.ready = ready

    async def check(self) -> bool:
        return self.ready


class StubResources:
    def __init__(self, *, postgres_ready: bool = True, qdrant_ready: bool = True) -> None:
        self.postgres_probe = StubProbe(postgres_ready)
        self.qdrant_probe = StubProbe(qdrant_ready)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:password@localhost:5432/database"},
        qdrant={"url": "http://localhost:6333", "embedding_dimension": 4},
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    resources = StubResources()

    async def factory(_: Settings) -> ApplicationResources:
        return cast(ApplicationResources, resources)

    app = create_app(settings, resource_factory=factory)
    with TestClient(app) as test_client:
        yield test_client
    assert resources.closed
