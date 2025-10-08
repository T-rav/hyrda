"""
Retrieval Service

Handles document retrieval and context building for RAG using Pinecone.
Includes adaptive query rewriting for improved retrieval accuracy.
"""

import logging
from typing import Any

from config.settings import Settings

from .query_rewriter import AdaptiveQueryRewriter
from .retrieval import PineconeRetrieval

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving and processing context from Pinecone vector store"""

    def __init__(
        self, settings: Settings, llm_service=None, enable_query_rewriting: bool = True
    ):
        self.settings = settings
        self.llm_service = llm_service
        self.enable_query_rewriting = enable_query_rewriting

        # Initialize Pinecone retrieval service
        self.pinecone_retrieval = PineconeRetrieval(settings)

        # Initialize query rewriter (will be lazy-loaded when LLM service is available)
        self.query_rewriter = None

    async def retrieve_context(
        self,
        query: str,
        vector_service,
        embedding_service,
        conversation_history: list[dict] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant context chunks for a query using provider-specific strategies.

        Applies adaptive query rewriting before retrieval to improve accuracy.

        Args:
            query: User query
            vector_service: Vector database service
            embedding_service: Embedding service for query encoding
            conversation_history: Recent conversation for context (optional)

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
                    query, conversation_history
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

            # Search using Pinecone
            results = await self.pinecone_retrieval.search(
                query,
                query_embedding,
                vector_service,
                metadata_filter=query_filters,
            )

            # Apply entity boosting to all results
            if results:
                results = self.pinecone_retrieval._apply_entity_boosting(query, results)

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
            final_results = self.pinecone_retrieval._apply_diversification_strategy(
                filtered_results
            )

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
    ) -> list[dict[str, Any]]:
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
            diversified_results = (
                self.pinecone_retrieval._apply_diversification_strategy(results)
            )

            logger.info(
                f"📚 Retrieved {len(diversified_results)} context chunks "
                f"using document similarity"
            )

            return diversified_results

        except Exception as e:
            logger.error(f"Error retrieving context by embedding: {e}")
            return []
