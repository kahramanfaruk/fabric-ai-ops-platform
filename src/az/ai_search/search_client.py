"""Azure AI Search client wrapper for hybrid (vector + keyword) retrieval.

Exposes a minimal, typed interface so the GenAI RAG chain is decoupled
from SDK internals.  All network I/O is synchronous; async variants can
be added without breaking the public API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from azure.core.exceptions import HttpResponseError
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from src.common.exceptions import IndexingError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """Single ranked document returned by a search query.

    Parameters
    ----------
    id : str
        Unique document identifier.
    content : str
        Text content of the document chunk.
    score : float
        Re-ranked relevance score (higher is better).
    metadata : dict[str, Any]
        Arbitrary key-value metadata attached to the document.
    """

    id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class OperationsSearchClient:
    """High-level wrapper around Azure AI Search for the operations index.

    Parameters
    ----------
    endpoint : str
        HTTPS endpoint of the AI Search service.
    index_name : str
        Name of the target search index.
    api_key : str
        Search service query key (retrieved from Key Vault at call site).
    """

    def __init__(self, endpoint: str, index_name: str, api_key: str) -> None:
        from azure.core.credentials import AzureKeyCredential

        self._client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key),
        )
        self._index_name = index_name

    def hybrid_search(
        self,
        query: str,
        vector: list[float] | None = None,
        top_k: int = 5,
        filter_expr: str | None = None,
    ) -> list[SearchResult]:
        """Execute a hybrid keyword + vector search.

        When *vector* is None, falls back to pure keyword (BM25) retrieval.

        Parameters
        ----------
        query : str
            Natural-language query string.
        vector : list[float] | None
            Pre-computed query embedding.  If provided, enables vector
            similarity re-ranking via Reciprocal Rank Fusion.
        top_k : int
            Maximum number of results to return.
        filter_expr : str | None
            OData filter expression for metadata pre-filtering.

        Returns
        -------
        list[SearchResult]
            Ranked list of matching document chunks.

        Raises
        ------
        IndexingError
            If the search service returns an HTTP error.
        """
        vector_queries = []
        if vector is not None:
            vector_queries.append(
                VectorizedQuery(vector=vector, k_nearest_neighbors=top_k, fields="content_vector")
            )
        try:
            raw = self._client.search(
                search_text=query,
                vector_queries=vector_queries or None,  # type: ignore[arg-type]
                filter=filter_expr,
                top=top_k,
                select=["id", "content", "metadata"],
            )
            results = [
                SearchResult(
                    id=doc["id"],
                    content=doc.get("content", ""),
                    score=doc.get("@search.score", 0.0),
                    metadata=doc.get("metadata", {}),
                )
                for doc in raw
            ]
        except HttpResponseError as exc:
            raise IndexingError(
                f"AI Search query failed on index '{self._index_name}': "
                f"status={exc.status_code}, reason={exc.reason}"
            ) from exc

        logger.debug(
            "Hybrid search returned %d results for query '%s'.",
            len(results),
            query[:80],
        )
        return results
