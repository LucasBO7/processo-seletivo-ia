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
    assert settings.llm_fast.model == "openai/gpt-oss-20b"
    assert settings.llm_fast.temperature == 0
    assert settings.llm_heavy.model == "openai/gpt-oss-120b"
    assert settings.llm_heavy.temperature == 0.1
    assert settings.query_planner.max_query_length == 2_000
    assert settings.query_planner.max_repair_attempts == 1
    assert settings.retriever.max_results == 20
    assert settings.retriever.excerpt_length == 1_000
    assert settings.extractor.max_sources_per_startup == 10
    assert settings.extractor.max_context_characters == 12_000
    assert settings.extractor.max_repair_attempts == 1
    assert settings.startup_classifier.max_sources_per_startup == 10
    assert settings.startup_classifier.max_context_characters == 12_000
    assert settings.startup_classifier.max_repair_attempts == 1
    assert settings.evidence_validator.max_sources_per_startup == 10
    assert settings.evidence_validator.max_items_per_startup == 250
    assert settings.evidence_validator.max_items_per_model_call == 10
    assert settings.evidence_validator.max_repair_attempts == 1
    assert settings.knowledge_ingestion.pipeline_version == "knowledge-v1"
    assert settings.knowledge_ingestion.chunk_max_characters == 1_500
    assert settings.knowledge_ingestion.chunk_overlap_characters == 150
    assert settings.nvidia_rag.vector_top_k == 20
    assert settings.nvidia_rag.lexical_top_k == 20
    assert settings.nvidia_rag.max_attempts == 3
    assert settings.nvidia_rag.vector_weight + settings.nvidia_rag.lexical_weight == 1
    assert settings.recommendation.max_recommendations_per_startup == 10
    assert settings.recommendation.max_repair_attempts == 1
    assert settings.briefing.max_startups == 20
    assert settings.briefing.max_markdown_characters == 50_000
    assert settings.briefing.max_repair_attempts == 1


def test_nvidia_rag_rejects_invalid_weights_and_limits() -> None:
    with pytest.raises(ValidationError, match="weights"):
        Settings(
            _env_file=None,
            postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
            qdrant={"url": "http://localhost:6333"},
            nvidia_rag={"vector_weight": 0.8, "lexical_weight": 0.8},
        )

    with pytest.raises(ValidationError, match="rerank_top_n"):
        Settings(
            _env_file=None,
            postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
            qdrant={"url": "http://localhost:6333"},
            nvidia_rag={"fused_top_k": 5, "rerank_top_n": 6},
        )


def test_recommendation_limits_parse_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECOMMENDATION__MAX_NEEDS_PER_STARTUP", "8")
    monkeypatch.setenv("RECOMMENDATION__MAX_NVIDIA_CHUNKS", "6")
    monkeypatch.setenv("RECOMMENDATION__MAX_REPAIR_ATTEMPTS", "0")
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
    )

    assert settings.recommendation.max_needs_per_startup == 8
    assert settings.recommendation.max_nvidia_chunks == 6
    assert settings.recommendation.max_repair_attempts == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_recommendations_per_startup", 51),
        ("max_context_characters", 999),
        ("max_repair_attempts", 2),
    ],
)
def test_recommendation_rejects_invalid_limits(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(
            _env_file=None,
            postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
            qdrant={"url": "http://localhost:6333"},
            recommendation={field: value},
        )


def test_briefing_limits_parse_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIEFING__MAX_STARTUPS", "8")
    monkeypatch.setenv("BRIEFING__MAX_STATEMENTS", "6")
    monkeypatch.setenv("BRIEFING__MAX_REPAIR_ATTEMPTS", "0")
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
    )

    assert settings.briefing.max_startups == 8
    assert settings.briefing.max_statements == 6
    assert settings.briefing.max_repair_attempts == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_startups", 101),
        ("max_context_characters", 999),
        ("max_repair_attempts", 2),
    ],
)
def test_briefing_rejects_invalid_limits(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(
            _env_file=None,
            postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
            qdrant={"url": "http://localhost:6333"},
            briefing={field: value},
        )


def test_knowledge_ingestion_rejects_invalid_overlap() -> None:
    with pytest.raises(ValidationError, match="overlap"):
        Settings(
            _env_file=None,
            postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
            qdrant={"url": "http://localhost:6333"},
            knowledge_ingestion={
                "chunk_max_characters": 200,
                "chunk_overlap_characters": 200,
            },
        )


def test_retriever_limits_parse_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVER__MAX_RESULTS", "10")
    monkeypatch.setenv("RETRIEVER__EXCERPT_LENGTH", "500")
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
    )

    assert settings.retriever.max_results == 10
    assert settings.retriever.excerpt_length == 500


def test_extractor_limits_parse_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR__MAX_SOURCES_PER_STARTUP", "5")
    monkeypatch.setenv("EXTRACTOR__MAX_CONTEXT_CHARACTERS", "5000")
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
    )

    assert settings.extractor.max_sources_per_startup == 5
    assert settings.extractor.max_context_characters == 5_000


def test_classifier_limits_parse_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STARTUP_CLASSIFIER__MAX_SIGNALS", "7")
    monkeypatch.setenv("STARTUP_CLASSIFIER__MAX_JUSTIFICATION_LENGTH", "700")
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
    )

    assert settings.startup_classifier.max_signals == 7
    assert settings.startup_classifier.max_justification_length == 700


def test_evidence_validator_limits_parse_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVIDENCE_VALIDATOR__MAX_ITEMS_PER_STARTUP", "100")
    monkeypatch.setenv("EVIDENCE_VALIDATOR__MAX_CONTEXT_CHARACTERS", "9000")
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
    )

    assert settings.evidence_validator.max_items_per_startup == 100
    assert settings.evidence_validator.max_context_characters == 9_000


def test_query_planner_limits_parse_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERY_PLANNER__MAX_QUERY_LENGTH", "500")
    monkeypatch.setenv("QUERY_PLANNER__MAX_ITEMS_PER_LIST", "10")
    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
    )

    assert settings.query_planner.max_query_length == 500
    assert settings.query_planner.max_items_per_list == 10


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_query_length", 2_001),
        ("max_items_per_list", 21),
        ("max_clarification_questions", 4),
        ("max_rationale_length", 501),
        ("max_repair_attempts", 2),
    ],
)
def test_query_planner_limits_reject_values_above_contract(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(
            _env_file=None,
            postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
            qdrant={"url": "http://localhost:6333"},
            query_planner={field: value},
        )


def test_llm_profiles_parse_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_FAST__MODEL", "fast-override")
    monkeypatch.setenv("LLM_FAST__TEMPERATURE", "0.25")
    monkeypatch.setenv("LLM_FAST__MAX_TOKENS", "4096")
    monkeypatch.setenv("LLM_FAST__TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("LLM_FAST__MAX_RETRIES", "1")
    monkeypatch.setenv("LLM_HEAVY__MODEL", "heavy-override")

    settings = Settings(
        _env_file=None,
        postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
        qdrant={"url": "http://localhost:6333"},
    )

    assert settings.llm_fast.model == "fast-override"
    assert settings.llm_fast.temperature == 0.25
    assert settings.llm_fast.max_tokens == 4096
    assert settings.llm_fast.timeout_seconds == 12
    assert settings.llm_fast.max_retries == 1
    assert settings.llm_heavy.model == "heavy-override"


@pytest.mark.parametrize(
    ("profile", "value"),
    [
        ({"model": "", "temperature": 0}, "model"),
        ({"model": "model", "temperature": -0.1}, "temperature"),
        ({"model": "model", "temperature": 0, "timeout_seconds": 0}, "timeout"),
        ({"model": "model", "temperature": 0, "max_retries": 11}, "max_retries"),
        ({"model": "model", "temperature": 0, "max_tokens": 512}, "max_tokens"),
    ],
)
def test_llm_profile_limits_are_validated(profile: dict[str, object], value: str) -> None:
    with pytest.raises(ValidationError, match=value):
        Settings(
            _env_file=None,
            postgres={"url": "postgresql+psycopg://user:secret@localhost/database"},
            qdrant={"url": "http://localhost:6333"},
            llm_fast=profile,
        )


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
        groq={"api_key": "groq-secret"},
    )

    representation = repr(settings)
    assert "top-secret" not in representation
    assert "qdrant-secret" not in representation
    assert "groq-secret" not in representation
