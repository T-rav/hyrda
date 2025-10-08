"""
Pinecone Retrieval Service

Pinecone-specific retrieval logic and optimizations.
"""

import logging
from typing import Any

from .base_retrieval import BaseRetrieval

logger = logging.getLogger(__name__)


class PineconeRetrieval(BaseRetrieval):
    """Pinecone-specific retrieval implementation"""

    async def search(
        self,
        query: str,
        query_embedding: list[float],
        vector_service,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Pinecone-specific search logic.

        Args:
            query: User query
            query_embedding: Query embedding vector
            vector_service: Pinecone vector service
            metadata_filter: Optional metadata filters from query rewriting

        Returns:
            Search results from Pinecone
        """
        logger.info("🔍 Using Pinecone pure vector similarity search")
        # Use lower threshold for entity boosting pipeline
        initial_threshold = max(0.1, self.settings.rag.similarity_threshold - 0.2)
        return await vector_service.search(
            query_embedding=query_embedding,
            limit=self.settings.rag.max_results * 3,  # Higher limit for entity boosting
            similarity_threshold=initial_threshold,
            filter=metadata_filter,
        )
