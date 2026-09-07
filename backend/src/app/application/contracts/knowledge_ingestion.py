from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class NvidiaTechnology(StrEnum):
    NVIDIA_INCEPTION = "nvidia_inception"
    NVIDIA_NIM = "nvidia_nim"
    NVIDIA_NEMO = "nvidia_nemo"
    NEMO_GUARDRAILS = "nemo_guardrails"
    TRITON_INFERENCE_SERVER = "triton_inference_server"
    TENSORRT_LLM = "tensorrt_llm"
    RAPIDS = "rapids"
    CUDF = "cudf"
    CUML = "cuml"
    CUDA = "cuda"
    RIVA = "riva"
    OMNIVERSE = "omniverse"
    ISAAC = "isaac"
    CLARA = "clara"
    MORPHEUS = "morpheus"
    NVIDIA_AI_ENTERPRISE = "nvidia_ai_enterprise"


class KnowledgeContentType(StrEnum):
    HTML = "html"
    MARKDOWN = "markdown"
    TEXT = "text"


class KnowledgeSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=120)
    technology: NvidiaTechnology
    canonical_url: HttpUrl
    content_type: KnowledgeContentType
    extractor: str = Field(min_length=1, max_length=40)
    required: bool = True
    enabled: bool = True


class SourceManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1, max_length=40)
    allowed_domains: tuple[str, ...] = Field(min_length=1)
    sources: tuple[KnowledgeSource, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity_and_coverage(self) -> SourceManifest:
        keys = [item.source_key for item in self.sources]
        urls = [str(item.canonical_url) for item in self.sources]
        if len(keys) != len(set(keys)):
            raise ValueError("source_key duplicado no manifesto")
        if len(urls) != len(set(urls)):
            raise ValueError("URL canônica duplicada no manifesto")
        domains = {value.lower() for value in self.allowed_domains}
        for source in self.sources:
            host = (source.canonical_url.host or "").lower()
            path = (source.canonical_url.path or "").lower()
            if source.canonical_url.scheme != "https":
                raise ValueError("fontes do manifesto devem usar HTTPS")
            if host not in domains:
                raise ValueError("domínio de fonte fora da allowlist")
            if host == "github.com" and not path.startswith("/nvidia/"):
                raise ValueError("repositório GitHub deve pertencer à organização NVIDIA")
        covered = {item.technology for item in self.sources if item.enabled and item.required}
        missing = set(NvidiaTechnology) - covered
        if missing:
            raise ValueError(f"tecnologias obrigatórias ausentes: {sorted(missing)}")
        return self


class FetchedKnowledgeContent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    content_type: KnowledgeContentType
    published_at: datetime | None = None


class NormalizedKnowledgeDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID
    source_key: str
    title: str
    technology: NvidiaTechnology
    source_url: str
    content_type: KnowledgeContentType
    content: str
    published_at: datetime | None
    ingested_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    pipeline_version: str


class PreparedKnowledgeChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: UUID
    document_id: UUID
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata: dict[str, Any]


class IngestionOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    FAILED = "failed"


class SourceIngestionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_key: str
    outcome: IngestionOutcome
    document_id: UUID | None = None
    chunks: int = Field(default=0, ge=0)
    error_code: str | None = None


class IngestionReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_version: str
    dry_run: bool
    results: tuple[SourceIngestionResult, ...]

    def count(self, outcome: IngestionOutcome) -> int:
        return sum(item.outcome is outcome for item in self.results)


class KnowledgeVerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    documents: int = Field(ge=0)
    chunks: int = Field(ge=0)
    vector_points: int = Field(ge=0)
    bm25_fingerprint: str
    missing_technologies: tuple[NvidiaTechnology, ...] = ()
    issues: tuple[str, ...] = ()
