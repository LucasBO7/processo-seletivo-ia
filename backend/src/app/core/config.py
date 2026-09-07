from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    SecretStr,
    field_validator,
    model_validator,
)
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


class StartupClassifierConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_sources_per_startup: int = Field(default=10, ge=1, le=50)
    max_context_characters: int = Field(default=12_000, ge=100, le=100_000)
    max_justification_length: int = Field(default=1_000, ge=50, le=4_000)
    max_signals: int = Field(default=20, ge=1, le=50)
    max_signal_description_length: int = Field(default=500, ge=50, le=2_000)
    max_repair_attempts: int = Field(default=1, ge=0, le=1)


class EvidenceValidatorConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_sources_per_startup: int = Field(default=10, ge=1, le=50)
    max_items_per_startup: int = Field(default=250, ge=1, le=500)
    max_context_characters: int = Field(default=20_000, ge=100, le=200_000)
    max_justification_length: int = Field(default=1_000, ge=50, le=4_000)
    max_repair_attempts: int = Field(default=1, ge=0, le=1)


class KnowledgeIngestionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    manifest_path: Path = BACKEND_ROOT / "scripts" / "nvidia_sources.json"
    pipeline_version: str = Field(default="knowledge-v1", min_length=1, max_length=40)
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    request_max_retries: int = Field(default=2, ge=0, le=5)
    max_source_bytes: int = Field(default=5_000_000, ge=1_000, le=50_000_000)
    chunk_max_characters: int = Field(default=1_500, ge=100, le=10_000)
    chunk_overlap_characters: int = Field(default=150, ge=0, le=2_000)
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    max_concurrency: int = Field(default=4, ge=1, le=16)

    @field_validator("manifest_path", mode="before")
    @classmethod
    def resolve_manifest_path(cls, value: object) -> Path:
        path = Path(str(value))
        return path if path.is_absolute() else BACKEND_ROOT / path

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> Self:
        if self.chunk_overlap_characters >= self.chunk_max_characters:
            raise ValueError("chunk overlap deve ser menor que o tamanho do chunk")
        return self


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
    startup_classifier: StartupClassifierConfig = StartupClassifierConfig()
    evidence_validator: EvidenceValidatorConfig = EvidenceValidatorConfig()
    knowledge_ingestion: KnowledgeIngestionConfig = KnowledgeIngestionConfig()
    embeddings: ModelProviderConfig = Field(
        default_factory=lambda: ModelProviderConfig(provider="unset", model="unset")
    )
    reranker: ModelProviderConfig = Field(
        default_factory=lambda: ModelProviderConfig(provider="cohere", model="rerank-v3.5")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
