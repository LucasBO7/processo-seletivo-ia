from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.application.contracts.query_plan import QueryPlan
from app.application.contracts.retrieval import RankedStartup, StartupSearchCriteria, TeamSizeRange
from app.core.config import RetrieverConfig
from app.domain.models import RecoverableError, Startup, StartupDocument
from app.graph.agents.retriever import RetrieverAgent, build_search_criteria, parse_team_size
from app.graph.contracts import GraphNode
from app.graph.state import AppState


def query_plan(**overrides: object) -> QueryPlan:
    payload: dict[str, object] = {
        "status": "ready",
        "normalized_query": "startups",
        "filters": {},
        "analysis_strategy": {
            "mode": "exploratory",
            "objectives": ["descobrir startups"],
            "rationale": "Consulta executável.",
        },
        "ambiguities": [],
        "clarification_questions": [],
    }
    payload.update(overrides)
    return QueryPlan.model_validate(payload)


class FakeStartupRepository:
    def __init__(
        self, results: list[RankedStartup] | None = None, error: Exception | None = None
    ) -> None:
        self.results = results or []
        self.error = error
        self.calls: list[tuple[StartupSearchCriteria, int]] = []

    async def add(self, startup: Startup) -> Startup:
        return startup

    async def get(self, startup_id: UUID) -> Startup | None:
        del startup_id
        return None

    async def search(self, criteria: StartupSearchCriteria, *, limit: int) -> list[RankedStartup]:
        self.calls.append((criteria, limit))
        if self.error:
            raise self.error
        return self.results


class FakeDocumentRepository:
    def __init__(
        self, documents: list[StartupDocument] | None = None, error: Exception | None = None
    ) -> None:
        self.documents = documents or []
        self.error = error
        self.calls: list[list[UUID]] = []

    async def add(self, document: StartupDocument) -> StartupDocument:
        return document

    async def list_for_startup(self, startup_id: UUID) -> list[StartupDocument]:
        return [item for item in self.documents if item.startup_id == startup_id]

    async def list_for_startups(self, startup_ids: list[UUID]) -> list[StartupDocument]:
        self.calls.append(startup_ids)
        if self.error:
            raise self.error
        return [item for item in self.documents if item.startup_id in startup_ids]


def agent(
    startups: FakeStartupRepository | None = None,
    documents: FakeDocumentRepository | None = None,
    config: RetrieverConfig | None = None,
) -> RetrieverAgent:
    return RetrieverAgent(
        startups=startups or FakeStartupRepository(),
        documents=documents or FakeDocumentRepository(),
        config=config or RetrieverConfig(),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("micro", TeamSizeRange(1, 10)),
        ("Pequena", TeamSizeRange(11, 50)),
        ("média", TeamSizeRange(51, 200)),
        ("large", TeamSizeRange(201)),
        ("25", TeamSizeRange(25, 25)),
        ("10-40", TeamSizeRange(10, 40)),
        ("50 ou mais", TeamSizeRange(50)),
        ("até 12", TeamSizeRange(0, 12)),
        ("desconhecido", None),
    ],
)
def test_parses_company_sizes(value: str, expected: TeamSizeRange | None) -> None:
    assert parse_team_size(value) == expected


def test_rejects_invalid_team_size_range() -> None:
    with pytest.raises(ValueError, match="invalid team size range"):
        TeamSizeRange(10, 5)


def test_builds_normalized_search_criteria_from_query_plan() -> None:
    plan = query_plan(
        filters={
            "sectors": ["FinTech"],
            "company_sizes": ["pequena", "20-30"],
            "stages": ["Seed"],
            "locations": ["São Paulo"],
            "keywords": ["Crédito", "crédito"],
            "ai_usage_signals": ["Machine Learning"],
        }
    )

    criteria = build_search_criteria(plan)

    assert criteria.sectors == ("fintech / crédito", "saas de gestão financeira")
    assert criteria.stages == ("seed",)
    assert criteria.locations == ("são paulo",)
    assert criteria.text_terms == ("crédito", "machine learning")
    assert criteria.team_size_ranges == (TeamSizeRange(11, 50), TeamSizeRange(20, 30))
    assert criteria.structured_filter_count == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "code"),
    [
        (AppState(), "retriever_plan_missing"),
        (
            AppState(query_plan=query_plan(status="invalid")),
            "retriever_plan_not_ready",
        ),
    ],
)
async def test_does_not_query_repository_without_ready_plan(state: AppState, code: str) -> None:
    startups = FakeStartupRepository()
    update = await agent(startups=startups)(state)

    assert update["errors"][0].code == code
    assert startups.calls == []


@pytest.mark.asyncio
async def test_returns_ranked_startups_and_ordered_traceable_sources() -> None:
    first = Startup(id=uuid4(), name="Alpha")
    second = Startup(id=uuid4(), name="Beta")
    ranked = [RankedStartup(first, 4.0), RankedStartup(second, 2.0)]
    newer = StartupDocument(
        id=uuid4(),
        startup_id=first.id,
        document_type="site",
        title="Zeta",
        content_text=" Evidência   mais recente " + "x" * 100,
        source_url="https://alpha.example/new",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    older = StartupDocument(
        id=uuid4(),
        startup_id=first.id,
        document_type="site",
        title="Alpha",
        content_text="Evidência antiga",
        source_url="https://alpha.example/old",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    second_document = StartupDocument(
        id=uuid4(),
        startup_id=second.id,
        document_type="site",
        title="Beta",
        content_text="Fonte beta",
        source_url="https://beta.example",
    )
    documents = FakeDocumentRepository([second_document, older, newer])

    update = await agent(
        startups=FakeStartupRepository(ranked),
        documents=documents,
        config=RetrieverConfig(excerpt_length=50),
    )(AppState(query_plan=query_plan(), metrics={"planner_ms": 1.0}))

    assert [item["startup_id"] for item in update["candidate_startups"]] == [
        first.id,
        second.id,
    ]
    assert [source.source_id for source in update["selected_sources"]] == [
        newer.id,
        older.id,
        second_document.id,
    ]
    assert update["selected_sources"][0].source_url == "https://alpha.example/new"
    assert len(update["selected_sources"][0].excerpt or "") == 50
    assert documents.calls == [[first.id, second.id]]
    assert update["metrics"]["planner_ms"] == 1.0


@pytest.mark.asyncio
async def test_keeps_startup_without_documents() -> None:
    startup = Startup(name="Sem fonte")
    update = await agent(startups=FakeStartupRepository([RankedStartup(startup, 1.0)]))(
        AppState(query_plan=query_plan())
    )

    assert update["candidate_startups"][0]["startup_id"] == startup.id
    assert update["selected_sources"] == []
    assert update["warnings"] == ["retriever_no_sources"]


@pytest.mark.asyncio
async def test_empty_search_returns_warning_without_document_query() -> None:
    documents = FakeDocumentRepository()
    update = await agent(documents=documents)(AppState(query_plan=query_plan()))

    assert update["candidate_startups"] == []
    assert update["selected_sources"] == []
    assert update["warnings"] == ["retriever_no_results"]
    assert update["errors"] == []
    assert documents.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_at", ["startups", "documents"])
async def test_persistence_failure_is_sanitized(failure_at: str) -> None:
    secret = RuntimeError("postgresql://user:secret@host/database")
    startup = Startup(name="Alpha")
    startups = FakeStartupRepository(
        [RankedStartup(startup, 1.0)], secret if failure_at == "startups" else None
    )
    documents = FakeDocumentRepository(error=secret if failure_at == "documents" else None)

    update = await agent(startups, documents)(
        AppState(
            query_plan=query_plan(),
            warnings=["existing"],
            errors=[RecoverableError(code="previous", message="Previous")],
        )
    )

    assert update["errors"][-1].code == "retriever_unavailable"
    assert "secret" not in repr(update)
    assert update["warnings"] == ["existing"]


def test_retriever_satisfies_graph_node_contract() -> None:
    node = cast(GraphNode, agent())
    assert isinstance(node, RetrieverAgent)
