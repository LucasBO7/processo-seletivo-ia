from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.application.contracts.knowledge_ingestion import NvidiaTechnology, SourceManifest
from app.infrastructure.ingestion.manifest import load_manifest

MANIFEST = Path(__file__).parents[2] / "scripts" / "nvidia_sources.json"


def test_official_manifest_covers_every_required_technology() -> None:
    manifest = load_manifest(MANIFEST)

    covered = {item.technology for item in manifest.sources if item.required and item.enabled}

    assert covered == set(NvidiaTechnology)
    assert len({item.source_key for item in manifest.sources}) == len(manifest.sources)
    assert all(str(item.canonical_url).startswith("https://") for item in manifest.sources)


def test_manifest_rejects_unapproved_domain() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload["sources"][0]["canonical_url"] = "https://example.com/source"

    with pytest.raises(ValidationError, match="allowlist"):
        SourceManifest.model_validate(payload)
