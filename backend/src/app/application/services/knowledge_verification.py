from __future__ import annotations

from app.application.contracts.knowledge_ingestion import (
    KnowledgeVerificationReport,
    NvidiaTechnology,
    SourceManifest,
)
from app.application.ports.knowledge import (
    KnowledgeIngestionRepository,
    KnowledgeLexicalIndex,
    KnowledgeVectorStore,
)


async def verify_knowledge_base(
    manifest: SourceManifest,
    repository: KnowledgeIngestionRepository,
    vectors: KnowledgeVectorStore,
    lexical_index: KnowledgeLexicalIndex,
) -> KnowledgeVerificationReport:
    documents = await repository.list_documents()
    chunks = await repository.list_chunks()
    vector_ids = await vectors.list_ids()
    vector_metadata = await vectors.list_metadata()
    document_by_id = {item.id: item for item in documents}
    chunk_ids = {item.id for item in chunks}
    issues: list[str] = []
    covered: set[NvidiaTechnology] = set()
    source_keys = {item.source_key for item in documents}
    required = {item.source_key: item.technology for item in manifest.sources if item.required}
    for key, technology in required.items():
        if key in source_keys:
            covered.add(technology)
    for chunk in chunks:
        document = document_by_id.get(chunk.document_id)
        if document is None:
            issues.append(f"orphan_chunk:{chunk.id}")
        elif chunk.metadata.get("source_url") != document.source_url:
            issues.append(f"source_url_mismatch:{chunk.id}")
        vector_url = vector_metadata.get(chunk.id, {}).get("source_url")
        if chunk.id in vector_ids and vector_url != chunk.metadata.get("source_url"):
            issues.append(f"vector_source_url_mismatch:{chunk.id}")
    missing_vectors = chunk_ids - vector_ids
    orphan_vectors = vector_ids - chunk_ids
    issues.extend(f"missing_vector:{item}" for item in sorted(missing_vectors, key=str))
    issues.extend(f"orphan_vector:{item}" for item in sorted(orphan_vectors, key=str))
    missing = tuple(sorted(set(NvidiaTechnology) - covered, key=lambda item: item.value))
    if missing:
        issues.append("knowledge_required_coverage_missing")
    return KnowledgeVerificationReport(
        valid=not issues,
        documents=len(documents),
        chunks=len(chunks),
        vector_points=len(vector_ids),
        bm25_fingerprint=lexical_index.build_and_fingerprint(chunks),
        missing_technologies=missing,
        issues=tuple(issues),
    )
