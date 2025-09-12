"""
Retrieval Service

Handles document retrieval and context building for RAG.
Routes to provider-specific retrieval implementations.
"""

import logging
from typing import Any

from config.settings import Settings
from .retrieval import ElasticsearchRetrieval, PineconeRetrieval

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving and processing context from vector stores"""

    def __init__(self, settings: Settings):
        self.settings = settings

        # Initialize provider-specific retrieval services
        self.elasticsearch_retrieval = ElasticsearchRetrieval(settings)
        self.pinecone_retrieval = PineconeRetrieval(settings)

    async def retrieve_context(
        self,
        query: str,
        vector_service,
        embedding_service,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant context chunks for a query using provider-specific strategies.

        Args:
            query: User query
            vector_service: Vector database service
            embedding_service: Embedding service for query encoding

        Returns:
            List of relevant context chunks with metadata
        """
        if not vector_service:
            logger.info("No vector service available, returning empty context")
            return []

        try:
            # Get query embedding
            query_embedding = await embedding_service.get_embedding(query)

            # Route to provider-specific search logic
            if self.settings.vector.provider.lower() == "elasticsearch":
                results = await self.elasticsearch_retrieval.search(
                    query, query_embedding, vector_service
                )
            elif self.settings.vector.provider.lower() == "pinecone":
                results = await self.pinecone_retrieval.search(
                    query, query_embedding, vector_service
                )
            else:
                logger.warning(
                    f"Unknown vector provider: {self.settings.vector.provider}"
                )
                results = []

            # Get the appropriate retrieval service for shared operations
            if self.settings.vector.provider.lower() == "elasticsearch":
                retrieval_service = self.elasticsearch_retrieval
            else:
                retrieval_service = self.pinecone_retrieval

            # Apply entity boosting to all results (regardless of hybrid search setting)
            if results:
                results = retrieval_service._apply_entity_boosting(query, results)

            # Apply hybrid search boosting if enabled
            if self.settings.rag.enable_hybrid_search and results:
                results = self._apply_hybrid_search_boosting(query, results)

            # Apply final similarity threshold filter
            filtered_results = [
                result
                for result in results
                if result.get("similarity", 0)
                >= self.settings.rag.results_similarity_threshold
            ]

            # Apply diversification strategy and limit to max results
            final_results = retrieval_service._apply_diversification_strategy(
                filtered_results
            )

            logger.info(
                f"📄 Retrieved {len(final_results)} context chunks (filtered by {self.settings.rag.results_similarity_threshold:.0%} threshold)"
            )
            return final_results

        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []

    def _apply_hybrid_search_boosting(
        self, query: str, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Apply hybrid search boosting to return multiple chunks per document.

        Args:
            query: User query for relevance scoring
            results: Initial search results

        Returns:
            Boosted results with multiple chunks per top documents
        """
        if not results:
            return results

        logger.debug(f"🔄 Applying hybrid search boosting to {len(results)} results")

        # Group results by document and get all chunks from top 5 documents
        seen_documents = set()
        final_results = []

        for result in results:
            metadata = result.get("metadata", {})
            file_name = metadata.get("file_name", "Unknown")

            # If we haven't seen this document, add it to our set
            if file_name not in seen_documents:
                seen_documents.add(file_name)
                # Stop if we already have enough unique documents
                if len(seen_documents) > self.settings.rag.max_results:
                    break

            # Add chunk if it's from one of our selected documents
            if (
                file_name in seen_documents
                and len(seen_documents) <= self.settings.rag.max_results
            ):
                final_results.append(result)

        logger.debug(
            f"📊 Hybrid boosting: Selected {len(final_results)} chunks "
            f"from {len(seen_documents)} documents"
        )

        return final_results
