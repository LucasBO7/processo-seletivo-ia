from __future__ import annotations

import hashlib
from collections.abc import Sequence

import httpx

from app.core.config import ModelProviderConfig


class OpenAICompatibleEmbeddingModel:
    def __init__(
        self, config: ModelProviderConfig, *, client: httpx.AsyncClient | None = None
    ) -> None:
        if config.base_url is None or config.api_key is None:
            raise ValueError("embedding provider requires base_url and api_key")
        self._model = config.model
        self._max_retries = config.max_retries
        self._endpoint = str(config.base_url).rstrip("/") + "/embeddings"
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=str(config.base_url).rstrip("/") + "/",
            timeout=config.timeout_seconds,
            headers={"Authorization": f"Bearer {config.api_key.get_secret_value()}"},
        )

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(
                    self._endpoint, json={"model": self._model, "input": list(texts)}
                )
                response.raise_for_status()
                data = response.json()["data"]
                ordered = sorted(data, key=lambda item: int(item["index"]))
                return [[float(value) for value in item["embedding"]] for item in ordered]
            except httpx.HTTPStatusError as error:
                transient = error.response.status_code == 429 or error.response.status_code >= 500
                if not transient or attempt == self._max_retries:
                    raise RuntimeError("knowledge_embedding_unavailable") from error
            except (httpx.RequestError, KeyError, TypeError, ValueError) as error:
                if attempt == self._max_retries:
                    raise RuntimeError("knowledge_embedding_unavailable") from error
        raise RuntimeError("knowledge_embedding_unavailable")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class DeterministicEmbeddingModel:
    """Offline model allowed only for dry-runs and deterministic tests."""

    def __init__(self, dimension: int) -> None:
        self._dimension = dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append(
                [
                    ((digest[index % len(digest)] / 255.0) * 2) - 1
                    for index in range(self._dimension)
                ]
            )
        return vectors
