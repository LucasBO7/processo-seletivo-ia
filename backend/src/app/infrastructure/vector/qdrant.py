from __future__ import annotations

from qdrant_client import AsyncQdrantClient, models

from app.core.config import QdrantConfig


def create_qdrant_client(config: QdrantConfig) -> AsyncQdrantClient:
    api_key = config.api_key.get_secret_value() if config.api_key else None
    return AsyncQdrantClient(
        url=str(config.url),
        api_key=api_key,
        timeout=config.timeout_seconds,
    )


def _distance(value: str) -> models.Distance:
    return {
        "cosine": models.Distance.COSINE,
        "dot": models.Distance.DOT,
        "euclid": models.Distance.EUCLID,
    }[value]


async def ensure_collection(client: AsyncQdrantClient, config: QdrantConfig) -> None:
    expected_distance = _distance(config.distance)
    if not await client.collection_exists(config.collection_name):
        await client.create_collection(
            collection_name=config.collection_name,
            vectors_config=models.VectorParams(
                size=config.embedding_dimension,
                distance=expected_distance,
            ),
        )
        return

    collection = await client.get_collection(config.collection_name)
    vectors = collection.config.params.vectors
    if not isinstance(vectors, models.VectorParams):
        raise RuntimeError("A coleção Qdrant deve usar um único vetor sem nome.")
    if vectors.size != config.embedding_dimension or vectors.distance != expected_distance:
        raise RuntimeError(
            "A coleção Qdrant existente não corresponde à dimensão ou distância configurada."
        )


class QdrantReadinessProbe:
    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    async def check(self) -> bool:
        try:
            await self._client.get_collections()
        except Exception:
            return False
        return True
