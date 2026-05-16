"""Unit tests for OperationsRAGChain.

All Azure SDK and OpenAI client calls are mocked so the chain logic
(prompt assembly, context building, error propagation) can be tested
in isolation without network I/O.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.az.ai_search.search_client import SearchResult
from src.common.exceptions import PlatformError
from src.genai.rag_chain import OperationsRAGChain, RAGResponse


def _make_chain() -> tuple[OperationsRAGChain, MagicMock, MagicMock]:
    oai = MagicMock()
    search = MagicMock()
    chain = OperationsRAGChain(
        openai_client=oai,
        search_client=search,
        chat_deployment="gpt-4o",
        embedding_deployment="text-embedding-3-small",
        top_k=3,
    )
    return chain, oai, search


class TestOperationsRAGChain:
    def test_returns_rag_response_with_answer(self) -> None:
        chain, oai, search = _make_chain()
        oai.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )
        search.hybrid_search.return_value = [
            SearchResult(id="doc-1", content="The pump failed due to cavitation.", score=0.9)
        ]
        mock_msg = MagicMock()
        mock_msg.content = "The pump failed due to cavitation at high flow rates."
        oai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=mock_msg)]
        )
        result = chain.invoke("Why did the pump fail?")
        assert isinstance(result, RAGResponse)
        assert "cavitation" in result.answer
        assert result.source_ids == ["doc-1"]

    def test_raises_on_empty_question(self) -> None:
        chain, _, _ = _make_chain()
        with pytest.raises(ValueError, match="non-empty"):
            chain.invoke("   ")

    def test_propagates_embedding_error(self) -> None:
        from openai import APIConnectionError as OAIConnectionError
        chain, oai, _ = _make_chain()
        oai.embeddings.create.side_effect = OAIConnectionError(request=MagicMock())
        with pytest.raises(PlatformError, match="Embedding call failed"):
            chain.invoke("test question")

    def test_empty_search_results_still_returns_answer(self) -> None:
        chain, oai, search = _make_chain()
        oai.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.0] * 1536)]
        )
        search.hybrid_search.return_value = []
        mock_msg = MagicMock()
        mock_msg.content = "I do not have enough information."
        oai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=mock_msg)]
        )
        result = chain.invoke("Unknown question?")
        assert result.context_chunks == []
        assert result.source_ids == []
