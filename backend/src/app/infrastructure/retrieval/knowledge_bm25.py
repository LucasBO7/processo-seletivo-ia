from __future__ import annotations

from collections.abc import Sequence

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
