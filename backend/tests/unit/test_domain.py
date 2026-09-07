from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models import Evidence, SourceReference, Startup, utc_now


def test_evidence_requires_a_source() -> None:
    with pytest.raises(ValueError, match="ao menos uma fonte"):
        Evidence(claim="A startup usa IA.", sources=())


def test_domain_defaults_use_uuid_and_utc() -> None:
    startup = Startup(name="Exemplo")

    assert startup.id
    assert startup.created_at.tzinfo is not None
    assert utc_now().tzinfo is not None


def test_evidence_accepts_traceable_source() -> None:
    source = SourceReference(
        startup_id=uuid4(),
        source_id=uuid4(),
        source_url="https://example.com/evidence",
        title="Fonte",
    )

    evidence = Evidence(claim="Afirmação", sources=(source,))

    assert evidence.sources[0].source_id == source.source_id
