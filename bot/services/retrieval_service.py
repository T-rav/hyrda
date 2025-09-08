"""
Retrieval Service

Handles document retrieval and context building for RAG.
Includes entity extraction, search result combination, and hybrid search boosting.
"""

import logging
import re
from typing import Any

from config.settings import Settings

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving and processing context from vector stores"""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def retrieve_context(
        self,
        query: str,
        vector_service,
        embedding_service,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant context chunks for a query using various search strategies.

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

            if self.settings.rag.enable_hybrid_search:
                logger.info("🔍 Using hybrid search with entity boosting")
                results = await self._search_with_entity_filtering(
                    query, query_embedding, vector_service
                )
            # Check if we're using Elasticsearch for traditional BM25 + vector boost
            elif (
                hasattr(vector_service, "bm25_search")
                and self.settings.vector.provider.lower() == "elasticsearch"
            ):
                logger.info("🔍 Using Elasticsearch BM25 + vector boost search")
                results = await vector_service.search(
                    query_embedding=query_embedding,
                    query_text=query,  # Pass query text for BM25 + vector boost
                    limit=self.settings.rag.max_results * 2,  # Get more for filtering
                    similarity_threshold=self.settings.rag.similarity_threshold,
                )
            else:
                # Pure vector similarity search (Pinecone or Elasticsearch without text)
                logger.info("🔍 Using pure vector similarity search")
                results = await vector_service.search(
                    query_embedding=query_embedding,
                    limit=self.settings.rag.max_results * 2,  # Get more for filtering
                    similarity_threshold=self.settings.rag.similarity_threshold,
                )

            # Apply hybrid search boosting if enabled
            if self.settings.rag.enable_hybrid_search and results:
                results = self._apply_hybrid_search_boosting(query, results)

            # Limit to final result count
            final_results = results[: self.settings.rag.max_results]

            logger.info(f"📄 Retrieved {len(final_results)} context chunks")
            return final_results

        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []

    def _extract_entities_simple(self, query: str) -> set[str]:
        """
        Simple entity extraction using patterns and keywords.

        Args:
            query: User query text

        Returns:
            Set of potential entity terms
        """
        entities = set()

        # Extract quoted terms (exact phrases)
        quoted_terms = re.findall(r'"([^"]*)"', query)
        entities.update(quoted_terms)

        # Extract capitalized words (potential proper nouns)
        capitalized_words = re.findall(r"\b[A-Z][a-z]+\b", query)
        entities.update(capitalized_words)

        # Technical terms and acronyms
        technical_terms = re.findall(r"\b[A-Z]{2,}\b", query)  # ALL CAPS
        entities.update(technical_terms)

        # Common business/tech entities
        business_keywords = [
            "API",
            "SDK",
            "database",
            "server",
            "client",
            "application",
            "system",
            "service",
            "platform",
            "framework",
            "library",
            "authentication",
            "authorization",
            "security",
            "encryption",
        ]

        query_lower = query.lower()
        for keyword in business_keywords:
            if keyword.lower() in query_lower:
                entities.add(keyword)

        # Remove single characters and common words
        entities = {
            e
            for e in entities
            if len(e) > 2
            and e.lower() not in {"the", "and", "for", "are", "but", "not"}
        }

        return entities

    async def _search_with_entity_filtering(
        self,
        query: str,
        query_embedding: list[float],
        vector_service,
    ) -> list[dict[str, Any]]:
        """
        Enhanced search with entity-aware filtering and boosting.

        Args:
            query: User query
            query_embedding: Query embedding vector
            vector_service: Vector database service

        Returns:
            Enhanced search results with entity boosting
        """
        try:
            # Extract entities from query
            entities = self._extract_entities_simple(query)
            logger.debug(f"🔍 Extracted entities: {entities}")

            # Get broader results for entity filtering
            base_results = await vector_service.search(
                query_embedding=query_embedding,
                limit=self.settings.rag.max_results * 3,  # Get more for filtering
                similarity_threshold=max(
                    0.1, self.settings.rag.similarity_threshold - 0.2
                ),
            )

            if not base_results:
                return []

            # Boost results that contain entities
            enhanced_results = []
            for result in base_results:
                content = result.get("content", "").lower()
                metadata = result.get("metadata", {})

                # Calculate entity boost
                entity_boost = 0.0
                matching_entities = 0

                for entity in entities:
                    if entity.lower() in content:
                        entity_boost += 0.05  # 5% boost per entity
                        matching_entities += 1

                    # Check title/filename for entities
                    title = metadata.get("file_name", "").lower()
                    if entity.lower() in title:
                        entity_boost += 0.1  # 10% boost for title match
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
                f"🎯 Entity filtering: {len(entities)} entities found, "
                f"boosted {sum(1 for r in enhanced_results if r['_entity_boost'] > 0)} results"
            )

            return enhanced_results

        except Exception as e:
            logger.error(f"Entity filtering failed: {e}")
            # Fallback to basic search
            return await vector_service.search(
                query_embedding=query_embedding,
                limit=self.settings.rag.max_results,
                similarity_threshold=self.settings.rag.similarity_threshold,
            )

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

    def _combine_search_results(
        self,
        vector_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Combine results from multiple search strategies.

        Args:
            vector_results: Results from vector similarity search
            keyword_results: Optional results from keyword/BM25 search

        Returns:
            Combined and deduplicated results
        """
        if not keyword_results:
            return vector_results

        # Simple combination - merge and deduplicate by content hash
        all_results = vector_results.copy()
        seen_content = {hash(r.get("content", "")) for r in vector_results}

        for result in keyword_results:
            content_hash = hash(result.get("content", ""))
            if content_hash not in seen_content:
                # Add with adjusted similarity score to indicate keyword match
                result["_search_type"] = "keyword"
                all_results.append(result)
                seen_content.add(content_hash)

        # Sort by similarity score
        all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)

        logger.debug(
            f"🔗 Combined {len(vector_results)} vector + {len(keyword_results or [])} keyword = {len(all_results)} total"
        )

        return all_results
