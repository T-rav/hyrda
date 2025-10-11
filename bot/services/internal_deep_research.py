"""
Internal Deep Research Service

Performs comprehensive research on complex queries using internal knowledge base.
Uses query decomposition, adaptive rewriting, and iterative retrieval for thorough answers.
"""

import logging
from typing import Any

from services.langfuse_service import observe

logger = logging.getLogger(__name__)


class InternalDeepResearchService:
    """
    Service for performing deep research on internal knowledge base.

    Uses multi-query retrieval with adaptive query rewriting to gather
    comprehensive context from the vector database.
    """

    def __init__(
        self,
        llm_service,
        retrieval_service,
        vector_service,
        embedding_service,
        enable_query_rewriting: bool = True,
    ):
        """
        Initialize internal deep research service.

        Args:
            llm_service: LLM service for query decomposition and synthesis
            retrieval_service: Retrieval service with query rewriting
            vector_service: Vector database service
            embedding_service: Embedding service
            enable_query_rewriting: Whether to use adaptive query rewriting
        """
        self.llm_service = llm_service
        self.retrieval_service = retrieval_service
        self.vector_service = vector_service
        self.embedding_service = embedding_service
        self.enable_query_rewriting = enable_query_rewriting

    @observe(as_type="generation", name="internal_deep_research")
    async def deep_research(
        self,
        query: str,
        effort: str = "medium",
        conversation_history: list[dict] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Perform deep research on internal knowledge base.

        Args:
            query: Research query
            effort: Research effort level - "low" (3 queries), "medium" (2 queries), "high" (1 query)
            conversation_history: Recent conversation for context
            user_id: User ID for resolving "me/I" references

        Returns:
            Dict with:
                - success: Whether research succeeded
                - query: Original query
                - sub_queries: List of generated sub-queries
                - chunks: All retrieved context chunks (deduplicated)
                - summary: Synthesized summary of findings
                - unique_documents: Number of unique documents found
                - total_chunks: Total number of chunks retrieved
        """
        if not self.vector_service:
            logger.warning("Vector service not available for internal deep research")
            return {
                "success": False,
                "error": "Vector database not configured",
                "query": query,
            }

        try:
            # Determine number of sub-queries based on effort (reduced by ~50% for cost savings)
            num_queries = {"low": 3, "medium": 2, "high": 1}.get(effort, 2)

            logger.info(
                f"🔍 Starting internal deep research ({effort} effort): {query}"
            )

            # Step 1: Decompose query into sub-queries
            sub_queries = await self._decompose_query(query, num_queries)
            logger.info(
                f"📋 Generated {len(sub_queries)} sub-queries for comprehensive search"
            )

            # Step 2: Retrieve context for each sub-query
            all_chunks = []
            unique_chunk_ids = set()

            for idx, sub_query in enumerate(sub_queries, 1):
                logger.info(f"🔎 Retrieving for sub-query {idx}/{len(sub_queries)}")

                chunks = await self.retrieval_service.retrieve_context(
                    sub_query,
                    self.vector_service,
                    self.embedding_service,
                    conversation_history=conversation_history,
                    user_id=user_id,
                )

                # Deduplicate chunks based on content hash
                for chunk in chunks:
                    chunk_id = self._get_chunk_id(chunk)
                    if chunk_id not in unique_chunk_ids:
                        unique_chunk_ids.add(chunk_id)
                        # Add source sub-query to metadata for traceability
                        chunk["metadata"]["sub_query"] = sub_query
                        all_chunks.append(chunk)

            # Step 3: Rank and limit chunks
            ranked_chunks = self._rank_chunks(all_chunks, query)

            # Limit to top chunks (scale with effort)
            max_chunks = {"low": 10, "medium": 15, "high": 20}.get(effort, 15)
            final_chunks = ranked_chunks[:max_chunks]

            logger.info(
                f"📊 Deep research complete: {len(final_chunks)} unique chunks from {len(unique_chunk_ids)} total retrieved"
            )

            # Step 4: Generate synthesis summary
            summary = await self._synthesize_findings(query, final_chunks, sub_queries)

            # Calculate statistics
            unique_documents = len(
                {
                    chunk.get("metadata", {}).get("file_name", "unknown")
                    for chunk in final_chunks
                }
            )

            return {
                "success": True,
                "query": query,
                "sub_queries": sub_queries,
                "chunks": final_chunks,
                "summary": summary,
                "unique_documents": unique_documents,
                "total_chunks": len(final_chunks),
                "effort": effort,
            }

        except Exception as e:
            logger.error(f"Internal deep research failed: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e), "query": query}

    @observe(as_type="generation", name="query_decomposition")
    async def _decompose_query(self, query: str, num_queries: int) -> list[str]:
        """
        Decompose complex query into multiple focused sub-queries.

        Args:
            query: Original complex query
            num_queries: Number of sub-queries to generate

        Returns:
            List of sub-queries covering different aspects
        """
        prompt = f"""You are a research query planner. Break down this complex research query into {num_queries} focused sub-queries that will help retrieve comprehensive information from an internal knowledge base.

Original Query: "{query}"

Generate {num_queries} specific sub-queries that:
1. Cover different aspects/angles of the main query
2. Are specific enough to retrieve relevant documents
3. Together provide comprehensive coverage of the topic
4. Avoid redundancy between queries

Format your response as a JSON array of strings:
["sub-query 1", "sub-query 2", ..., "sub-query {num_queries}"]

Return ONLY the JSON array, no explanation."""

        response = await self.llm_service.get_response(
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            import json

            sub_queries = json.loads(response.strip())

            # Validate response
            if isinstance(sub_queries, list) and len(sub_queries) > 0:
                logger.info(
                    f"✅ Generated {len(sub_queries)} sub-queries for: {query[:50]}..."
                )
                return sub_queries
            else:
                logger.warning(f"Invalid sub-query format: {response}")
                # Fallback: use original query
                return [query]

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse sub-queries: {response}")
            # Fallback: use original query
            return [query]

    def _get_chunk_id(self, chunk: dict) -> str:
        """
        Generate unique ID for chunk to enable deduplication.

        Args:
            chunk: Context chunk

        Returns:
            Unique identifier string
        """
        content = chunk.get("content", "")
        file_name = chunk.get("metadata", {}).get("file_name", "")

        # Use first 100 chars of content + file name as ID
        return f"{file_name}:{content[:100]}"

    def _rank_chunks(self, chunks: list[dict], query: str) -> list[dict]:
        """
        Rank chunks by relevance to original query.

        Args:
            chunks: List of context chunks
            query: Original query

        Returns:
            Sorted list of chunks (highest relevance first)
        """
        # Sort by similarity score (already included from retrieval)
        return sorted(chunks, key=lambda x: x.get("similarity", 0), reverse=True)

    @observe(as_type="generation", name="research_synthesis")
    async def _synthesize_findings(
        self, query: str, chunks: list[dict], sub_queries: list[str]
    ) -> str:
        """
        Synthesize findings from multiple chunks into a summary.

        Args:
            query: Original query
            chunks: Retrieved context chunks
            sub_queries: Sub-queries used for retrieval

        Returns:
            Synthesized summary of findings
        """
        if not chunks:
            return "No relevant information found in internal knowledge base."

        # Build context from chunks
        context_parts = []
        for idx, chunk in enumerate(chunks[:10], 1):  # Limit to top 10 for synthesis
            file_name = chunk.get("metadata", {}).get("file_name", "unknown")
            content = chunk.get("content", "")[:500]  # Truncate long chunks
            context_parts.append(f"[Source {idx}: {file_name}]\n{content}")

        context = "\n\n".join(context_parts)

        # Generate synthesis
        prompt = f"""You are a research synthesizer. Based on the internal knowledge base documents below, provide a comprehensive answer to the research query.

Research Query: "{query}"

Sub-queries explored:
{chr(10).join(f"{i}. {sq}" for i, sq in enumerate(sub_queries, 1))}

Retrieved Context:
{context}

Provide a well-structured, comprehensive answer that:
1. Directly addresses the research query
2. Synthesizes information from multiple sources
3. Highlights key findings and insights
4. Notes any gaps or areas with limited information

Keep your response focused and informative (2-3 paragraphs)."""

        synthesis = await self.llm_service.get_response(
            messages=[{"role": "user", "content": prompt}]
        )

        return synthesis or "Unable to synthesize findings."


class _InternalDeepResearchServiceSingleton:
    """Singleton holder for internal deep research service."""

    _instance: InternalDeepResearchService | None = None

    @classmethod
    def get_instance(cls) -> InternalDeepResearchService | None:
        """
        Get singleton internal deep research service instance.

        Lazy-loads the service with dependencies from the global service registry.
        Returns None if required services are not available.

        Returns:
            Initialized InternalDeepResearchService or None if services unavailable
        """
        if cls._instance is not None:
            return cls._instance

        try:
            # Import here to avoid circular dependencies
            from config.settings import get_settings
            from services.embedding_service import get_embedding_service
            from services.llm_service import LLMService
            from services.retrieval_service import RetrievalService
            from services.vector_service import get_vector_service

            settings = get_settings()

            # Check if vector storage is enabled
            if not settings.vector.enabled:
                logger.info(
                    "Vector storage disabled - internal deep research unavailable"
                )
                return None

            # Get required services
            vector_service = get_vector_service()
            embedding_service = get_embedding_service()
            llm_service = LLMService(settings)
            retrieval_service = RetrievalService(settings)

            if not all(
                [vector_service, embedding_service, llm_service, retrieval_service]
            ):
                logger.warning(
                    "Required services unavailable for internal deep research"
                )
                return None

            # Create singleton instance
            cls._instance = InternalDeepResearchService(
                llm_service=llm_service,
                retrieval_service=retrieval_service,
                vector_service=vector_service,
                embedding_service=embedding_service,
                enable_query_rewriting=True,
            )

            logger.info("Internal deep research service initialized")
            return cls._instance

        except Exception as e:
            logger.error(f"Failed to initialize internal deep research service: {e}")
            return None


def get_internal_deep_research_service() -> InternalDeepResearchService | None:
    """
    Get singleton internal deep research service instance.

    Returns:
        Initialized InternalDeepResearchService or None if services unavailable
    """
    return _InternalDeepResearchServiceSingleton.get_instance()


# Factory function
def create_internal_deep_research_service(
    llm_service, retrieval_service, vector_service, embedding_service
) -> InternalDeepResearchService:
    """
    Create internal deep research service instance.

    Args:
        llm_service: LLM service for query decomposition
        retrieval_service: Retrieval service with query rewriting
        vector_service: Vector database service
        embedding_service: Embedding service

    Returns:
        Initialized InternalDeepResearchService
    """
    return InternalDeepResearchService(
        llm_service=llm_service,
        retrieval_service=retrieval_service,
        vector_service=vector_service,
        embedding_service=embedding_service,
        enable_query_rewriting=True,
    )
