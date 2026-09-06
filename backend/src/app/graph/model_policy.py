from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from app.application.ports.providers import ChatModel, ChatModelError, ChatModelErrorCode
from app.graph.nodes import ALL_NODE_NAMES, NodeName


class ModelProfile(StrEnum):
    FAST = "fast"
    HEAVY = "heavy"


MODEL_PROFILE_BY_NODE: Mapping[NodeName, ModelProfile | None] = MappingProxyType(
    {
        NodeName.QUERY_PLANNER: ModelProfile.FAST,
        NodeName.RETRIEVER: None,
        NodeName.EXTRACTOR: ModelProfile.FAST,
        NodeName.STARTUP_CLASSIFIER: ModelProfile.HEAVY,
        NodeName.EVIDENCE_VALIDATOR: ModelProfile.FAST,
        NodeName.NVIDIA_RAG: ModelProfile.FAST,
        NodeName.RECOMMENDATION: ModelProfile.HEAVY,
        NodeName.BRIEFING: ModelProfile.HEAVY,
    }
)

if set(MODEL_PROFILE_BY_NODE) != set(ALL_NODE_NAMES):
    raise RuntimeError("Every graph node must have an explicit model allocation.")


def model_profile_for(node: NodeName) -> ModelProfile | None:
    return MODEL_PROFILE_BY_NODE[node]


@dataclass(frozen=True, slots=True)
class ModelRegistry:
    llm_fast: ChatModel
    llm_heavy: ChatModel

    def resolve(self, node: NodeName) -> ChatModel:
        profile = model_profile_for(node)
        if profile is None:
            raise ChatModelError(
                ChatModelErrorCode.MODEL_NOT_ALLOCATED,
                "This graph node does not use a chat model.",
            )
        if profile is ModelProfile.FAST:
            return self.llm_fast
        return self.llm_heavy
