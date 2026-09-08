from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.application.ports.knowledge import KnowledgeSearchHit
from app.application.ports.providers import RankedDocument
from app.domain.models import KnowledgeChunk
from app.infrastructure.retrieval.bm25 import BM25Retriever, bm25_corpus_fingerprint


class KnowledgeBM25Index:
    def build_and_fingerprint(self, chunks: Sequence[KnowledgeChunk]) -> str:
        corpus = [
            RankedDocument(document_id=str(item.id), text=item.content, score=0) for item in chunks
        ]
        BM25Retriever(corpus)
        return bm25_corpus_fingerprint(corpus)

    def search(
        self, query: str, chunks: Sequence[KnowledgeChunk], *, limit: int
    ) -> list[KnowledgeSearchHit]:
        corpus = [
            RankedDocument(document_id=str(item.id), text=item.content, score=0)
            for item in sorted(
                chunks, key=lambda item: (item.document_id, item.chunk_index, item.id)
            )
        ]
        results = BM25Retriever(corpus).search(query, top_n=limit)
        return [
            KnowledgeSearchHit(chunk_id=UUID(item.document_id), score=item.score)
            for item in results
        ]
