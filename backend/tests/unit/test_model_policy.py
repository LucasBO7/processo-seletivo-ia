from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.application.ports.providers import ChatMessage, ChatModelError, ChatModelErrorCode
from app.graph.model_policy import (
    MODEL_PROFILE_BY_NODE,
    ModelProfile,
    ModelRegistry,
    model_profile_for,
)
from app.graph.nodes import ALL_NODE_NAMES, NodeName


class StubChatModel:
    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        del messages
        return "ok"


@pytest.mark.parametrize(
    ("node", "profile"),
    [
        (NodeName.QUERY_PLANNER, ModelProfile.FAST),
        (NodeName.RETRIEVER, None),
        (NodeName.EXTRACTOR, ModelProfile.FAST),
        (NodeName.STARTUP_CLASSIFIER, ModelProfile.HEAVY),
        (NodeName.EVIDENCE_VALIDATOR, ModelProfile.FAST),
        (NodeName.NVIDIA_RAG, None),
        (NodeName.RECOMMENDATION, ModelProfile.HEAVY),
        (NodeName.BRIEFING, ModelProfile.HEAVY),
    ],
)
def test_every_node_has_the_expected_profile(node: NodeName, profile: ModelProfile | None) -> None:
    assert model_profile_for(node) is profile


def test_policy_is_exhaustive() -> None:
    assert set(MODEL_PROFILE_BY_NODE) == set(ALL_NODE_NAMES)


def test_registry_resolves_shared_models_and_rejects_retriever() -> None:
    fast = StubChatModel()
    heavy = StubChatModel()
    registry = ModelRegistry(llm_fast=fast, llm_heavy=heavy)

    assert registry.resolve(NodeName.QUERY_PLANNER) is fast
    assert registry.resolve(NodeName.STARTUP_CLASSIFIER) is heavy
    with pytest.raises(ChatModelError) as error:
        registry.resolve(NodeName.RETRIEVER)

    assert error.value.code is ChatModelErrorCode.MODEL_NOT_ALLOCATED
