from __future__ import annotations

import re
from collections.abc import Sequence

from rank_bm25 import BM25Okapi

from app.application.ports.providers import RankedDocument


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ÿ]+", text.lower())


class BM25Retriever:
    def __init__(self, documents: Sequence[RankedDocument]) -> None:
        self._documents = list(documents)
        self._index = (
            BM25Okapi([_tokenize(item.text) for item in self._documents])
            if self._documents
            else None
        )

    def search(self, query: str, *, top_n: int) -> list[RankedDocument]:
        if self._index is None or top_n <= 0:
            return []
        scores = self._index.get_scores(_tokenize(query))
        ranked = sorted(
            zip(self._documents, scores, strict=True),
            key=lambda item: float(item[1]),
            reverse=True,
        )[:top_n]
        return [
            RankedDocument(document_id=item.document_id, text=item.text, score=float(score))
            for item, score in ranked
        ]
