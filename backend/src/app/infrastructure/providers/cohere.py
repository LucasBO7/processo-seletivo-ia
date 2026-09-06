from __future__ import annotations

from collections.abc import Sequence

import cohere

from app.application.ports.providers import RankedDocument


class CohereReranker:
    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        self._client = cohere.AsyncClientV2(api_key=api_key, timeout=timeout_seconds)
        self._model = model

    async def rerank(
        self,
        query: str,
        documents: Sequence[RankedDocument],
        *,
        top_n: int,
    ) -> list[RankedDocument]:
        if not documents or top_n <= 0:
            return []
        response = await self._client.rerank(
            model=self._model,
            query=query,
            documents=[document.text for document in documents],
            top_n=min(top_n, len(documents)),
        )
        return [
            RankedDocument(
                document_id=documents[result.index].document_id,
                text=documents[result.index].text,
                score=result.relevance_score,
            )
            for result in response.results
        ]
