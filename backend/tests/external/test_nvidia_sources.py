from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.infrastructure.ingestion.http_source import HttpKnowledgeSourceClient
from app.infrastructure.ingestion.manifest import load_manifest

pytestmark = [pytest.mark.integration, pytest.mark.external]


async def test_explicit_external_source_fetch() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1" or os.getenv("RUN_EXTERNAL_TESTS") != "1":
        pytest.skip("Defina as flags de integração e fontes externas para executar.")
    manifest = load_manifest(Path(__file__).parents[2] / "scripts" / "nvidia_sources.json")
    client = HttpKnowledgeSourceClient(
        allowed_domains=set(manifest.allowed_domains),
        timeout_seconds=20,
        max_bytes=5_000_000,
    )
    try:
        fetched = await client.fetch(manifest.sources[0])
        assert fetched.body.strip()
    finally:
        await client.close()
