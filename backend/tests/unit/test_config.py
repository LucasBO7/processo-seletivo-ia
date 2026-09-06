from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_parse_nested_values() -> None:
    settings = Settings(
        _env_file=None,
        postgres={
            "url": "postgresql+psycopg://user:secret@localhost/database",
            "pool_size": 7,
        },
        qdrant={
            "url": "http://localhost:6333",
            "embedding_dimension": 768,
            "distance": "dot",
        },
        http={"cors_origins": ["http://localhost:5173"]},
    )

    assert settings.postgres.pool_size == 7
    assert settings.qdrant.embedding_dimension == 768
    assert settings.qdrant.distance == "dot"
    assert settings.reranker.provider == "cohere"


def test_settings_require_postgres_and_qdrant() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    message = str(error.value)
    assert "postgres" in message
    assert "qdrant" in message
    assert "secret" not in message


def test_cors_rejects_credentialed_wildcard() -> None:
    with pytest.raises(ValidationError, match="CORS"):
        Settings(
            _env_file=None,
            postgres={"url": "postgresql+psycopg://user:password@localhost/database"},
            qdrant={"url": "http://localhost:6333"},
            http={"cors_origins": ["*"], "cors_allow_credentials": True},
        )


def test_secret_values_are_redacted() -> None:
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:top-secret@localhost/database"},
        qdrant={"url": "http://localhost:6333", "api_key": "qdrant-secret"},
    )

    representation = repr(settings)
    assert "top-secret" not in representation
    assert "qdrant-secret" not in representation
