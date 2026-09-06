from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[3]


class AppConfig(BaseModel):
    name: str = "NVIDIA Startup AI Radar"
    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


class HttpConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    cors_allow_credentials: bool = False

    @model_validator(mode="after")
    def reject_credentialed_wildcard(self) -> Self:
        if self.cors_allow_credentials and "*" in self.cors_origins:
            raise ValueError("CORS não permite credenciais quando a origem é '*'.")
        return self


class PostgresConfig(BaseModel):
    url: SecretStr
    pool_size: int = Field(default=5, ge=1, le=50)
    max_overflow: int = Field(default=5, ge=0, le=100)
    connect_timeout_seconds: int = Field(default=5, gt=0, le=60)


class QdrantConfig(BaseModel):
    url: HttpUrl
    api_key: SecretStr | None = None
    collection_name: str = "nvidia_knowledge_v1"
    embedding_dimension: int = Field(default=1024, gt=0, le=65536)
    distance: Literal["cosine", "dot", "euclid"] = "cosine"
    timeout_seconds: int = Field(default=5, gt=0, le=60)


class ModelProviderConfig(BaseModel):
    provider: str
    model: str
    base_url: HttpUrl | None = None
    api_key: SecretStr | None = None
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_retries: int = Field(default=2, ge=0, le=10)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
    )

    app: AppConfig = Field(default_factory=AppConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    postgres: PostgresConfig
    qdrant: QdrantConfig
    chat: ModelProviderConfig = Field(
        default_factory=lambda: ModelProviderConfig(provider="unset", model="unset")
    )
    embeddings: ModelProviderConfig = Field(
        default_factory=lambda: ModelProviderConfig(provider="unset", model="unset")
    )
    reranker: ModelProviderConfig = Field(
        default_factory=lambda: ModelProviderConfig(provider="cohere", model="rerank-v3.5")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
