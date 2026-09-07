from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, model_validator
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


class GroqConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key: SecretStr | None = None


class LLMProfileConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_retries: int = Field(default=2, ge=0, le=10)


class QueryPlannerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_query_length: int = Field(default=2_000, ge=1, le=2_000)
    max_items_per_list: int = Field(default=20, ge=1, le=20)
    max_clarification_questions: int = Field(default=3, ge=1, le=3)
    max_rationale_length: int = Field(default=500, ge=1, le=500)
    max_repair_attempts: int = Field(default=1, ge=0, le=1)


class RetrieverConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_results: int = Field(default=20, ge=1, le=100)
    excerpt_length: int = Field(default=300, ge=50, le=2_000)


class ExtractorConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_sources_per_startup: int = Field(default=10, ge=1, le=50)
    max_context_characters: int = Field(default=12_000, ge=100, le=100_000)
    max_fact_length: int = Field(default=1_000, ge=50, le=4_000)
    max_items_per_list: int = Field(default=20, ge=1, le=50)
    max_repair_attempts: int = Field(default=1, ge=0, le=1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        extra="forbid",
        frozen=True,
    )

    app: AppConfig = Field(default_factory=AppConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    postgres: PostgresConfig
    qdrant: QdrantConfig
    groq: GroqConfig = GroqConfig()
    llm_fast: LLMProfileConfig = LLMProfileConfig(model="openai/gpt-oss-20b", temperature=0)
    llm_heavy: LLMProfileConfig = LLMProfileConfig(model="openai/gpt-oss-120b", temperature=0.1)
    query_planner: QueryPlannerConfig = QueryPlannerConfig()
    retriever: RetrieverConfig = RetrieverConfig()
    extractor: ExtractorConfig = ExtractorConfig()
    embeddings: ModelProviderConfig = Field(
        default_factory=lambda: ModelProviderConfig(provider="unset", model="unset")
    )
    reranker: ModelProviderConfig = Field(
        default_factory=lambda: ModelProviderConfig(provider="cohere", model="rerank-v3.5")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
