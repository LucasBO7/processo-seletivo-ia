from __future__ import annotations

from datetime import UTC, datetime

from app.application.contracts.knowledge_ingestion import (
    FetchedKnowledgeContent,
    KnowledgeContentType,
    KnowledgeSource,
    NvidiaTechnology,
)
from app.infrastructure.ingestion.normalization import normalize_document, normalize_text
from app.infrastructure.ingestion.preparer import DeterministicKnowledgePreparer


def source() -> KnowledgeSource:
    return KnowledgeSource(
        source_key="nvidia-nim",
        technology=NvidiaTechnology.NVIDIA_NIM,
        canonical_url="https://www.nvidia.com/en-us/nim/",
        content_type=KnowledgeContentType.HTML,
        extractor="web",
    )


def test_html_normalization_removes_noise_and_preserves_heading() -> None:
    result = normalize_text(
        "<nav>menu</nav><h1>NIM</h1><p>Inference   service.</p><script>bad()</script>",
        KnowledgeContentType.HTML,
    )

    assert "menu" not in result
    assert "bad" not in result
    assert "# NIM" in result
    assert "Inference service." in result


def test_document_and_chunks_are_deterministic_and_traceable() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    fetched = FetchedKnowledgeContent(
        title="NVIDIA NIM",
        body="<h1>Serving</h1><p>Optimized inference services.</p>",
        content_type=KnowledgeContentType.HTML,
    )
    preparer = DeterministicKnowledgePreparer(
        chunk_max_characters=100,
        chunk_overlap_characters=10,
    )

    first = preparer.prepare(
        source(), fetched, ingested_at=now, pipeline_version="v1", embedding_fingerprint="f"
    )
    second = preparer.prepare(
        source(), fetched, ingested_at=now, pipeline_version="v1", embedding_fingerprint="f"
    )
    document, chunks = first

    assert first == second
    assert document.source_url == "https://www.nvidia.com/en-us/nim/"
    assert chunks[0].document_id == document.document_id
    assert chunks[0].metadata["source_url"] == document.source_url
    assert chunks[0].metadata["source_section"] == "Serving"
    assert chunks[0].metadata["start_offset"] >= 0


def test_empty_document_is_rejected() -> None:
    fetched = FetchedKnowledgeContent(
        title="NIM", body="<nav>only noise</nav>", content_type=KnowledgeContentType.HTML
    )

    try:
        normalize_document(
            source(),
            fetched,
            ingested_at=datetime(2026, 9, 7, tzinfo=UTC),
            pipeline_version="v1",
        )
    except ValueError as error:
        assert str(error) == "knowledge_document_empty"
    else:
        raise AssertionError("empty document must fail")


def test_repeated_content_is_deduplicated_with_contiguous_indexes() -> None:
    fetched = FetchedKnowledgeContent(
        title="NIM",
        body="<p>Repeated block.</p><p>Repeated block.</p><p>Unique block.</p>",
        content_type=KnowledgeContentType.HTML,
    )
    preparer = DeterministicKnowledgePreparer(
        chunk_max_characters=100,
        chunk_overlap_characters=0,
    )

    _, chunks = preparer.prepare(
        source(),
        fetched,
        ingested_at=datetime(2026, 9, 7, tzinfo=UTC),
        pipeline_version="v1",
        embedding_fingerprint="f",
    )

    assert [item.content for item in chunks] == ["Repeated block.", "Unique block."]
    assert [item.chunk_index for item in chunks] == [0, 1]
    assert len({item.content_hash for item in chunks}) == len(chunks)
