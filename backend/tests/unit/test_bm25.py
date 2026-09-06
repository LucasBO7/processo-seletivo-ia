from app.application.ports.providers import RankedDocument
from app.infrastructure.retrieval.bm25 import BM25Retriever


def test_bm25_returns_the_most_relevant_document() -> None:
    retriever = BM25Retriever(
        [
            RankedDocument(document_id="voice", text="transcrição de voz", score=0),
            RankedDocument(document_id="data", text="processamento de dados", score=0),
        ]
    )

    result = retriever.search("voz", top_n=1)

    assert result[0].document_id == "voice"


def test_bm25_handles_empty_or_zero_limit() -> None:
    assert BM25Retriever([]).search("qualquer", top_n=5) == []
