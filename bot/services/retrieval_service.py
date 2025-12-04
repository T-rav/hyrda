"""
Retrieval Service

Handles document retrieval and context building for RAG using Qdrant.
Includes adaptive query rewriting for improved retrieval accuracy.
"""

import logging
import re

from bot_types import ContextChunk
from config.settings import Settings

from .query_rewriter import AdaptiveQueryRewriter

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving and processing context from Qdrant vector store"""

    def __init__(
        self, settings: Settings, llm_service=None, enable_query_rewriting: bool = True
    ):
        self.settings = settings
        self.llm_service = llm_service
        self.enable_query_rewriting = enable_query_rewriting

        # Initialize query rewriter (will be lazy-loaded when LLM service is available)
        self.query_rewriter = None

    async def retrieve_context(
        self,
        query: str,
        vector_service: object,
        embedding_service: object,
        conversation_history: list[dict] | None = None,
        user_id: str | None = None,
    ) -> list[ContextChunk]:
        """
        Retrieve relevant context chunks for a query.

        Applies adaptive query rewriting before retrieval to improve accuracy.

        Args:
            query: User query
            vector_service: Vector database service
            embedding_service: Embedding service for query encoding
            conversation_history: Recent conversation for context (optional)
            user_id: Slack user ID for resolving "me/I" references (optional)

        Returns:
            List of relevant context chunks with metadata
        """
        if not vector_service:
            logger.info("No vector service available, returning empty context")
            return []

        try:
            # Initialize query rewriter if not already done and LLM service is available
            if (
                self.enable_query_rewriting
                and not self.query_rewriter
                and self.llm_service
            ):
                self.query_rewriter = AdaptiveQueryRewriter(
                    self.llm_service, enable_rewriting=True
                )
                logger.info("✅ Query rewriter initialized")

            # Apply query rewriting if enabled
            rewritten_query = query
            query_filters = None

            if self.query_rewriter:
                rewrite_result = await self.query_rewriter.rewrite_query(
                    query, conversation_history, user_id
                )
                rewritten_query = rewrite_result["query"]
                query_filters = rewrite_result.get("filters", {})

                logger.info(
                    f"🔄 Query rewriting: strategy={rewrite_result['strategy']}, "
                    f"intent={rewrite_result.get('intent', {}).get('type', 'unknown')}"
                )
                if query_filters:
                    logger.info(f"🔍 Applying metadata filters: {query_filters}")
                logger.info(f"📝 Original query: '{query}'")
                logger.info(f"📝 Rewritten query: '{rewritten_query[:500]}'")
                if len(rewritten_query) > 500:
                    logger.info(f"   ... (truncated from {len(rewritten_query)} chars)")

            # Get query embedding (use rewritten query)
            query_embedding = await embedding_service.get_embedding(rewritten_query)

            # Search using vector service
            logger.info("🔍 Using vector similarity search")
            # Use lower threshold for entity boosting pipeline
            initial_threshold = max(0.1, self.settings.rag.similarity_threshold - 0.2)
            results = await vector_service.search(
                query_embedding=query_embedding,
                limit=self.settings.rag.max_results
                * 3,  # Higher limit for entity boosting
                similarity_threshold=initial_threshold,
                filter=query_filters,
            )

            # Apply entity boosting to all results
            if results:
                results = self._apply_entity_boosting(query, results)

            # Apply final similarity threshold filter
            filtered_results = [
                result
                for result in results
                if result.get("similarity", 0)
                >= self.settings.rag.results_similarity_threshold
            ]

            logger.info(
                f"🔽 Pre-filter: {len(results)} results, Post-filter: {len(filtered_results)} results (threshold: {self.settings.rag.results_similarity_threshold:.0%})"
            )

            # Apply diversification strategy and limit to max results
            final_results = self._apply_diversification_strategy(filtered_results)

            logger.info(f"📄 Retrieved {len(final_results)} final context chunks")
            if final_results:
                # Log first result for debugging
                first_result = final_results[0]
                logger.info(
                    f"   Top result: {first_result.get('metadata', {}).get('file_name', 'unknown')} "
                    f"(similarity: {first_result.get('similarity', 0):.2f})"
                )
            return final_results

        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []

    async def retrieve_context_by_embedding(
        self,
        document_embedding: list[float],
        vector_service,
    ) -> list[ContextChunk]:
        """
        Retrieve relevant context chunks using a document's embedding for similarity search.

        Args:
            document_embedding: Embedding vector of uploaded document
            vector_service: Vector storage service

        Returns:
            List of relevant chunks found using document similarity
        """
        try:
            logger.info("🔍 Retrieving context using document embedding similarity")

            # Search vector store using document embedding (no query text for pure vector search)
            results = await vector_service.search(
                query_embedding=document_embedding,
                limit=self.settings.rag.max_results * 2,  # Get more for diversity
                similarity_threshold=self.settings.rag.similarity_threshold,
                query_text="",  # No text query, pure vector similarity
            )

            if not results:
                logger.info("📭 No similar documents found in vector database")
                return []

            # Apply diversification to get chunks from different documents
            diversified_results = self._apply_diversification_strategy(results)

            logger.info(
                f"📚 Retrieved {len(diversified_results)} context chunks "
                f"using document similarity"
            )

            return diversified_results

        except Exception as e:
            logger.error(f"Error retrieving context by embedding: {e}")
            return []

    def _extract_entities_simple(self, query: str) -> set[str]:
        """
        Generic entity extraction: treat every significant word as an entity,
        just filter out common filler words.

        Args:
            query: User query text

        Returns:
            Set of entity terms (all significant words from query)
        """
        # Define comprehensive stop words to filter out
        stop_words = {
            # Articles, prepositions, conjunctions
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            # Common verbs
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            # Question words
            "what",
            "when",
            "where",
            "why",
            "how",
            "who",
            "which",
            "whose",
            # Pronouns
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "them",
            "this",
            "that",
            "these",
            "those",
            # Common adjectives/adverbs
            "any",
            "some",
            "all",
            "many",
            "much",
            "more",
            "most",
            "very",
            "really",
            "quite",
            # Modal verbs
            "can",
            "could",
            "will",
            "would",
            "should",
            "shall",
            "may",
            "might",
            "must",
            # Other common filler words
            "there",
            "here",
            "then",
            "than",
            "so",
            "just",
            "only",
            "also",
            "even",
            "still",
        }

        # Extract all words (2+ characters, alphanumeric)
        words = re.findall(r"\b[a-zA-Z0-9]{2,}\b", query.lower())

        # Filter out stop words and keep everything else as entities
        entities = {word for word in words if word not in stop_words}

        logger.debug(f"Extracted entities from '{query}': {entities}")
        return entities

    def _apply_entity_boosting(
        self, query: str, results: list[ContextChunk]
    ) -> list[ContextChunk]:
        """
        Apply entity boosting to search results.

        Args:
            query: User query for entity extraction
            results: Search results to boost

        Returns:
            Results with entity boosting applied
        """
        try:
            # Extract entities from query
            entities = self._extract_entities_simple(query)
            logger.debug(f"🔍 Applying entity boosting for entities: {entities}")

            # Boost results that contain entities
            enhanced_results = []
            for result in results:
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
                f"🎯 Entity boosting: {len(entities)} entities found, "
                f"boosted {sum(1 for r in enhanced_results if r['_entity_boost'] > 0)} results"
            )

            return enhanced_results

        except Exception as e:
            logger.error(f"Entity boosting failed: {e}")
            return results

    def _apply_diversification_strategy(
        self, results: list[ContextChunk]
    ) -> list[ContextChunk]:
        """
        Apply smart similarity-first diversification with automatic document chunk limiting.

        For document chunks (has file_name), limits to max 3 chunks per document to avoid
        overwhelming context. For metric data (employees, projects - no file_name), returns
        pure similarity order.

        Args:
            results: Filtered results ready for diversification

        Returns:
            Diversified results
        """
        if not results:
            return []

        max_results = self.settings.rag.max_results

        # Smart diversification: limit chunks per document, pure similarity for metric data
        return self._smart_similarity_diversify(results, max_results)

    def _smart_similarity_diversify(
        self, results: list[ContextChunk], max_results: int
    ) -> list[ContextChunk]:
        """
        Smart similarity-first diversification.

        - For document chunks (has file_name): Limit to RAG_MAX_CHUNKS_PER_DOCUMENT per document
        - For metric data (no file_name): Pure similarity order

        Args:
            results: Input results sorted by similarity
            max_results: Maximum total results to return

        Returns:
            Diversified results
        """
        if not results:
            return []

        selected = []
        doc_chunk_count = {}  # Track chunks per document
        max_per_doc = self.settings.rag.max_chunks_per_document

        for result in results:
            if len(selected) >= max_results:
                break

            file_name = result.get("metadata", {}).get("file_name")

            # If it's a document chunk (has file_name), limit per document
            if file_name and file_name != "Unknown":
                count = doc_chunk_count.get(file_name, 0)
                if count >= max_per_doc:
                    continue
                doc_chunk_count[file_name] = count + 1

            # For metric data (no file_name) or under limit, add by similarity
            selected.append(result)

        logger.debug(
            f"Smart diversification: Selected {len(selected)} results "
            f"({len(doc_chunk_count)} unique documents, max {max_per_doc} chunks per doc)"
        )

        return selected
