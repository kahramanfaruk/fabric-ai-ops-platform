"""Retrieval-Augmented Generation chain for the operations assistant.

Architecture
------------
1. Embed the user query via Azure OpenAI text-embedding-3-small.
2. Retrieve top-k context chunks from AI Search (hybrid: keyword + vector).
3. Build a grounded prompt and call the chat-completion model.
4. Optionally evaluate the response via the judge LLM.

This chain is intentionally stateless: no conversation history is stored
server-side.  Multi-turn support requires the caller to pass prior turns
as additional messages (not implemented here to keep scope minimal).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openai import APIConnectionError, APIStatusError, AzureOpenAI

from src.az.ai_search.search_client import OperationsSearchClient
from src.common.exceptions import PlatformError
from src.genai.prompt_templates import build_rag_messages

logger = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    """Output of a single RAG chain invocation.

    Parameters
    ----------
    answer : str
        Generated answer text.
    context_chunks : list[str]
        Raw retrieved context passages used for grounding.
    source_ids : list[str]
        Document IDs of the retrieved chunks (for citations).
    """

    answer: str
    context_chunks: list[str]
    source_ids: list[str]


class OperationsRAGChain:
    """End-to-end RAG chain for the grounded operations assistant.

    Parameters
    ----------
    openai_client : AzureOpenAI
        Authenticated Azure OpenAI client.
    search_client : OperationsSearchClient
        AI Search client configured for the operations index.
    chat_deployment : str
        Azure OpenAI chat model deployment name.
    embedding_deployment : str
        Azure OpenAI embedding model deployment name.
    top_k : int
        Number of context chunks to retrieve.
    """

    def __init__(
        self,
        openai_client: AzureOpenAI,
        search_client: OperationsSearchClient,
        chat_deployment: str,
        embedding_deployment: str = "text-embedding-3-small",
        top_k: int = 5,
    ) -> None:
        self._oai = openai_client
        self._search = search_client
        self._chat_deployment = chat_deployment
        self._embedding_deployment = embedding_deployment
        self._top_k = top_k

    def _embed(self, text: str) -> list[float]:
        """Embed *text* using the configured embedding deployment."""
        try:
            response = self._oai.embeddings.create(
                input=text, model=self._embedding_deployment
            )
            return response.data[0].embedding
        except (APIStatusError, APIConnectionError) as exc:
            raise PlatformError(
                f"Embedding call failed for deployment '{self._embedding_deployment}': {exc}"
            ) from exc

    def invoke(self, question: str) -> RAGResponse:
        """Execute the full RAG pipeline for *question*.

        Parameters
        ----------
        question : str
            User question string.  Must not be empty.

        Returns
        -------
        RAGResponse
            Grounded answer with supporting context and source IDs.

        Raises
        ------
        ValueError
            If *question* is empty.
        PlatformError
            If embedding, retrieval, or generation fails.
        """
        if not question.strip():
            raise ValueError("question must be a non-empty string.")

        query_vector = self._embed(question)
        results = self._search.hybrid_search(
            query=question, vector=query_vector, top_k=self._top_k
        )

        if not results:
            logger.warning("No context chunks retrieved for question: '%s'", question[:80])

        context_chunks = [r.content for r in results]
        source_ids = [r.id for r in results]
        context_str = "\n\n".join(
            f"[{i+1}] {chunk}" for i, chunk in enumerate(context_chunks)
        )

        messages = build_rag_messages(context=context_str, question=question)
        try:
            completion = self._oai.chat.completions.create(
                model=self._chat_deployment,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.0,
                max_tokens=512,
            )
        except (APIStatusError, APIConnectionError) as exc:
            raise PlatformError(
                f"Chat completion failed for deployment '{self._chat_deployment}': {exc}"
            ) from exc

        answer = completion.choices[0].message.content or ""
        logger.info(
            "RAG chain complete: retrieved=%d chunks, answer_len=%d chars",
            len(results),
            len(answer),
        )
        return RAGResponse(answer=answer, context_chunks=context_chunks, source_ids=source_ids)
