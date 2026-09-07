from __future__ import annotations

import json
from pathlib import Path

from app.application.contracts.knowledge_ingestion import SourceManifest


def load_manifest(path: Path) -> SourceManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("knowledge_source_invalid") from error
    return SourceManifest.model_validate(payload)
