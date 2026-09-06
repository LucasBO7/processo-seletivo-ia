from enum import StrEnum


class NodeName(StrEnum):
    QUERY_PLANNER = "query_planner"
    RETRIEVER = "retriever"
    EXTRACTOR = "extractor"
    STARTUP_CLASSIFIER = "startup_classifier"
    EVIDENCE_VALIDATOR = "evidence_validator"
    NVIDIA_RAG = "nvidia_rag"
    RECOMMENDATION = "recommendation"
    BRIEFING = "briefing"


ALL_NODE_NAMES: tuple[NodeName, ...] = tuple(NodeName)
