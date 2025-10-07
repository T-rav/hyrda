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
        if self.settings.rag.enable_hybrid_search:
            logger.info("🔍 Using Pinecone hybrid search with entity boosting")
            return await self._search_with_entity_filtering(
                query, query_embedding, vector_service, metadata_filter
            )
        else:
            logger.info("🔍 Using Pinecone pure vector similarity search")
            # Use lower threshold for entity boosting pipeline
            initial_threshold = max(0.1, self.settings.rag.similarity_threshold - 0.2)
            return await vector_service.search(
                query_embedding=query_embedding,
                limit=self.settings.rag.max_results
                * 3,  # Higher limit for entity boosting
                similarity_threshold=initial_threshold,
                filter=metadata_filter,
            )

    async def _search_with_entity_filtering(
        self,
        query: str,
        query_embedding: list[float],
        vector_service,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Enhanced search with entity-aware filtering and boosting for Pinecone.

        Args:
            query: User query
            query_embedding: Query embedding vector
            vector_service: Pinecone vector database service
            metadata_filter: Optional metadata filters from query rewriting

        Returns:
            Enhanced search results with entity boosting
        """
        try:
            # Extract entities from query
            entities = self._extract_entities_simple(query)
            logger.debug(f"🔍 Extracted entities: {entities}")

            # Get broader results for entity filtering with Pinecone-optimized limit
            base_results = await vector_service.search(
                query_embedding=query_embedding,
                limit=100,  # Higher limit for Pinecone to capture more documents for entity boosting
                similarity_threshold=max(
                    0.05, self.settings.rag.similarity_threshold - 0.25
                ),
                filter=metadata_filter,
            )

            if not base_results:
                return []

            # Apply entity boosting
            enhanced_results = []
            for result in base_results:
                content = result.get("content", "").lower()
                metadata = result.get("metadata", {})

                # Calculate entity boost
                entity_boost = 0.0
                matching_entities = 0

                for entity in entities:
                    if entity.lower() in content:
                        entity_boost += self.settings.rag.entity_content_boost
                        matching_entities += 1

                    # Check title/filename for entities
                    title = metadata.get("file_name", "").lower()
                    if entity.lower() in title:
                        entity_boost += self.settings.rag.entity_title_boost
                        matching_entities += 1

                # Apply boost to similarity score
                original_similarity = result.get("similarity", 0)
                boosted_similarity = min(1.0, original_similarity + entity_boost)

                # Add debug info
                result["_entity_boost"] = entity_boost
                result["_matching_entities"] = matching_entities
                result["_original_similarity"] = original_similarity
                result["similarity"] = boosted_similarity

                enhanced_results.append(result)

            # Sort by boosted similarity
            enhanced_results.sort(key=lambda x: x["similarity"], reverse=True)

            logger.debug(
                f"🎯 Pinecone entity filtering: {len(entities)} entities found, "
                f"boosted {sum(1 for r in enhanced_results if r['_entity_boost'] > 0)} results"
            )

            return enhanced_results

        except Exception as e:
            logger.error(f"Pinecone entity filtering failed: {e}")
            # Fallback to basic search
            return await vector_service.search(
                query_embedding=query_embedding,
                limit=self.settings.rag.max_results,
                similarity_threshold=self.settings.rag.similarity_threshold,
                filter=metadata_filter,
            )
