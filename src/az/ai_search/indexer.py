"""Batch document indexer for Azure AI Search.

Pushes documents produced by the Gold Lakehouse layer into the search
index with retry-aware upload and chunking to stay within the 32 MB
batch limit.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.search.documents import SearchClient

from src.common.exceptions import IndexingError

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500  # Conservative; SDK default is 1 000 but keeps payloads small.


def _chunk(items: list[Any], size: int) -> Iterator[list[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def upload_documents(
    endpoint: str,
    index_name: str,
    api_key: str,
    documents: list[dict[str, Any]],
) -> int:
    """Upload documents to an AI Search index in batches.

    Parameters
    ----------
    endpoint : str
        HTTPS endpoint of the AI Search service.
    index_name : str
        Target index name.
    api_key : str
        Admin key retrieved from Key Vault.
    documents : list[dict[str, Any]]
        Documents to upload.  Each must contain an 'id' field.

    Returns
    -------
    int
        Total number of documents successfully indexed.

    Raises
    ------
    IndexingError
        If any batch upload fails.
    """
    if not documents:
        logger.info("upload_documents called with empty document list; nothing to do.")
        return 0

    client = SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(api_key),
    )
    total_indexed = 0
    for batch in _chunk(documents, _BATCH_SIZE):
        try:
            results = client.upload_documents(documents=batch)
            failed = [r for r in results if not r.succeeded]
            if failed:
                keys = [r.key for r in failed]
                raise IndexingError(
                    f"{len(failed)} document(s) failed to index in '{index_name}': keys={keys}"
                )
            total_indexed += len(batch)
            logger.info("Indexed batch of %d documents.", len(batch))
        except HttpResponseError as exc:
            raise IndexingError(
                f"HTTP error during indexing to '{index_name}': {exc.reason}"
            ) from exc

    logger.info("Total documents indexed: %d", total_indexed)
    return total_indexed
