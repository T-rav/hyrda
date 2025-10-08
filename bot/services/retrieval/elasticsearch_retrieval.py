"""
Elasticsearch Retrieval Service

Elasticsearch-specific retrieval logic and optimizations.
"""

import logging
from typing import Any

from .base_retrieval import BaseRetrieval

logger = logging.getLogger(__name__)


class ElasticsearchRetrieval(BaseRetrieval):
    """Elasticsearch-specific retrieval implementation"""

    async def search(
        self,
        query: str,
        query_embedding: list[float],
        vector_service,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Elasticsearch-specific search logic.

        Args:
            query: User query
            query_embedding: Query embedding vector
            vector_service: Elasticsearch vector service
            metadata_filter: Optional metadata filters from query rewriting

        Returns:
            Search results from Elasticsearch
        """
        if hasattr(vector_service, "bm25_search"):
            logger.info("🔍 Using Elasticsearch BM25 + vector boost search")
            # Use lower threshold for entity boosting pipeline
            initial_threshold = max(0.1, self.settings.rag.similarity_threshold - 0.2)
            return await vector_service.search(
                query_embedding=query_embedding,
                query_text=query,  # Pass query text for BM25 + vector boost
                limit=50,  # Higher limit for Elasticsearch diversification
                similarity_threshold=initial_threshold,
                filter=metadata_filter,
            )
        else:
            logger.info("🔍 Using Elasticsearch pure vector similarity search")
            # Use lower threshold for entity boosting pipeline
            initial_threshold = max(0.1, self.settings.rag.similarity_threshold - 0.2)
            return await vector_service.search(
                query_embedding=query_embedding,
                limit=50,  # Higher limit for Elasticsearch diversification
                similarity_threshold=initial_threshold,
                filter=metadata_filter,
            )
