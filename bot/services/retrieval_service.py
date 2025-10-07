"""
Retrieval Service

Handles document retrieval and context building for RAG.
Routes to provider-specific retrieval implementations.
Includes adaptive query rewriting for improved retrieval accuracy.
"""

import logging
from typing import Any

from config.settings import Settings

from .query_rewriter import AdaptiveQueryRewriter
from .retrieval import ElasticsearchRetrieval, PineconeRetrieval

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving and processing context from vector stores"""

    def __init__(
        self, settings: Settings, llm_service=None, enable_query_rewriting: bool = True
    ):
        self.settings = settings
        self.llm_service = llm_service
        self.enable_query_rewriting = enable_query_rewriting

        # Initialize provider-specific retrieval services
        self.elasticsearch_retrieval = ElasticsearchRetrieval(settings)
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
                logger.debug(f"Original query: {query}")
                logger.debug(f"Rewritten query: {rewritten_query[:200]}...")

            # Get query embedding (use rewritten query)
            query_embedding = await embedding_service.get_embedding(rewritten_query)

            # Route to provider-specific search logic
            if self.settings.vector.provider.lower() == "elasticsearch":
                results = await self.elasticsearch_retrieval.search(
                    query,
                    query_embedding,
                    vector_service,
                    metadata_filter=query_filters,
                )
            elif self.settings.vector.provider.lower() == "pinecone":
                results = await self.pinecone_retrieval.search(
                    query,
                    query_embedding,
                    vector_service,
                    metadata_filter=query_filters,
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
            diversified_results = self._apply_hybrid_search_boosting("", results)

            logger.info(
                f"📚 Retrieved {len(diversified_results)} context chunks "
                f"using document similarity"
            )

            return diversified_results

        except Exception as e:
            logger.error(f"Error retrieving context by embedding: {e}")
            return []
