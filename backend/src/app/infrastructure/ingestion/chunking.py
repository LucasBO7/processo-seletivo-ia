from __future__ import annotations

from uuid import uuid5

from app.application.contracts.knowledge_ingestion import (
    NormalizedKnowledgeDocument,
    PreparedKnowledgeChunk,
)
from app.infrastructure.ingestion.normalization import KNOWLEDGE_NAMESPACE, sha256_text


def chunk_document(
    document: NormalizedKnowledgeDocument,
    *,
    max_characters: int,
    overlap_characters: int,
    embedding_fingerprint: str,
) -> tuple[PreparedKnowledgeChunk, ...]:
    if max_characters <= 0 or overlap_characters < 0 or overlap_characters >= max_characters:
        raise ValueError("knowledge_chunk_config_invalid")
    pieces = _section_pieces(document.content, max_characters)
    chunks: list[PreparedKnowledgeChunk] = []
    content_hashes: set[str] = set()
    cursor = 0
    previous_tail = ""
    for section, piece in pieces:
        combined = f"{previous_tail}\n{piece}".strip() if previous_tail else piece
        content = combined[:max_characters].strip()
        if not content:
            continue
        start = document.content.find(piece, cursor)
        start = cursor if start < 0 else start
        end = min(len(document.content), start + len(piece))
        cursor = end
        content_hash = sha256_text(content)
        if content_hash in content_hashes:
            previous_tail = content[-overlap_characters:] if overlap_characters else ""
            continue
        content_hashes.add(content_hash)
        index = len(chunks)
        chunk_id = uuid5(
            KNOWLEDGE_NAMESPACE,
            f"{document.document_id}:{document.content_hash}:{index}:{section}:{start}:{end}",
        )
        metadata = {
            "title": document.title,
            "technology": document.technology.value,
            "source_url": document.source_url,
            "source_key": document.source_key,
            "source_section": section,
            "start_offset": start,
            "end_offset": end,
            "ingested_at": document.ingested_at.isoformat(),
            "pipeline_version": document.pipeline_version,
            "embedding_fingerprint": embedding_fingerprint,
        }
        chunks.append(
            PreparedKnowledgeChunk(
                chunk_id=chunk_id,
                document_id=document.document_id,
                chunk_index=index,
                content=content,
                content_hash=content_hash,
                metadata=metadata,
            )
        )
        previous_tail = content[-overlap_characters:] if overlap_characters else ""
    if not chunks:
        raise ValueError("knowledge_document_empty")
    return tuple(chunks)


def _section_pieces(content: str, max_characters: int) -> list[tuple[str, str]]:
    section = "document"
    result: list[tuple[str, str]] = []
    blocks = [item.strip() for item in content.splitlines()]
    for block in blocks:
        if not block:
            continue
        if block.startswith("# "):
            section = block[2:].strip() or section
            continue
        while len(block) > max_characters:
            split = block.rfind(" ", 0, max_characters + 1)
            split = max_characters if split <= 0 else split
            result.append((section, block[:split].strip()))
            block = block[split:].strip()
        if block:
            result.append((section, block))
    return result
