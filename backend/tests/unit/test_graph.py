from __future__ import annotations

import json
from dataclasses import asdict
from uuid import uuid4

from app.domain.models import Evidence, SourceReference
from app.graph.builder import create_graph_builder
from app.graph.nodes import ALL_NODE_NAMES, NodeName
from app.graph.state import AppState, empty_state


def test_all_eight_node_names_are_centralized() -> None:
    assert len(ALL_NODE_NAMES) == 8
    assert NodeName.QUERY_PLANNER in ALL_NODE_NAMES
    assert NodeName.BRIEFING in ALL_NODE_NAMES


def test_state_accepts_partial_updates_and_traceable_evidence() -> None:
    source = SourceReference(
        source_id=uuid4(),
        source_url="https://example.com",
        title="Fonte",
    )
    state = empty_state(run_id=uuid4(), correlation_id="corr-1", query="fintechs")
    update = AppState(validated_claims=[Evidence(claim="Usa IA", sources=(source,))])
    state.update(update)

    encoded = json.dumps(
        {**state, "validated_claims": [asdict(item) for item in state["validated_claims"]]},
        default=str,
    )
    assert "https://example.com" in encoded
    assert "corr-1" in encoded


def test_builder_is_empty_until_a_functional_spec_adds_nodes() -> None:
    builder = create_graph_builder()

    assert builder.nodes == {}
