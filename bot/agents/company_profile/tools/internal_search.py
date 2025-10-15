"""Internal search tool for querying the internal knowledge base.

A self-contained LangChain tool that performs deep research on the vector database
using only LangChain primitives - no bot services.
"""

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class InternalSearchInput(BaseModel):
    """Input schema for internal search tool."""

    query: str = Field(
        min_length=3,
        description="What to search for in internal knowledge base. Be specific about what you're looking for. MUST be a meaningful search query (minimum 3 characters). DO NOT call with empty string.",
    )
    effort: str = Field(
        default="medium",
        description='Research depth - "low" (2 queries), "medium" (3 queries), "high" (5 queries). Default: "medium"',
    )


class InternalSearchTool(BaseTool):
    """Search the internal knowledge base (vector database) for existing information.

    Use this FIRST before web search to check if we already have information about:
    - Existing customers or past clients
    - Previous projects or engagements
    - Internal documentation
    - Historical company data

    This tool is self-contained and uses only LangChain primitives.
    """

    name: str = "internal_search_tool"
    description: str = (
        "Search the internal knowledge base for existing information. "
        "Use this FIRST before web search to check our internal docs, customer history, past projects, and internal documentation. "
        "IMPORTANT: Only call if you have a specific company name or topic to search for (minimum 3 characters). "
        "DO NOT call with empty query."
    )
    args_schema: type[BaseModel] = InternalSearchInput

    # LangChain components (injected at initialization)
    vector_store: Any = None  # LangChain VectorStore
    llm: Any = None  # LangChain ChatModel
    embeddings: Any = None  # LangChain Embeddings

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        vector_store: Any = None,
        llm: Any = None,
        embeddings: Any = None,
        **kwargs,
    ):
        """Initialize with LangChain components.

        Args:
            vector_store: LangChain VectorStore instance (e.g., Qdrant, Pinecone)
            llm: LangChain ChatModel (e.g., ChatOpenAI, ChatAnthropic)
            embeddings: LangChain Embeddings (e.g., OpenAIEmbeddings)
            **kwargs: Additional BaseTool arguments
        """
        # Pass components as kwargs to avoid Pydantic issues
        kwargs["vector_store"] = vector_store
        kwargs["llm"] = llm
        kwargs["embeddings"] = embeddings

        super().__init__(**kwargs)

        # Lazy-load if not provided
        if not all([self.vector_store, self.llm, self.embeddings]):
            self._initialize_components()

    def _initialize_components(self):
        """Initialize LangChain components from environment (fallback only).

        Uses environment variables matching .env file format.
        """
        try:
            import os

            # Get settings from environment (matching actual .env keys)
            llm_api_key = os.getenv("LLM_API_KEY")
            llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")

            embedding_api_key = os.getenv(
                "EMBEDDING_API_KEY", llm_api_key
            )  # Fallback to LLM key
            embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

            vector_provider = os.getenv("VECTOR_PROVIDER", "qdrant")
            vector_host = os.getenv("VECTOR_HOST", "localhost")
            vector_port = os.getenv("VECTOR_PORT", "6333")
            vector_api_key = os.getenv("VECTOR_API_KEY")
            vector_collection = os.getenv(
                "VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base"
            )

            # Initialize LangChain LLM
            if not self.llm and llm_api_key:
                from langchain_openai import ChatOpenAI

                self.llm = ChatOpenAI(
                    model=llm_model,
                    api_key=llm_api_key,
                    temperature=0,
                )
                logger.info(f"Initialized LLM: {llm_model}")

            # Initialize LangChain Embeddings
            if not self.embeddings and embedding_api_key:
                from langchain_openai import OpenAIEmbeddings

                self.embeddings = OpenAIEmbeddings(
                    model=embedding_model,
                    api_key=embedding_api_key,
                )
                logger.info(f"Initialized embeddings: {embedding_model}")

            # Initialize LangChain VectorStore
            if (
                not self.vector_store
                and vector_provider == "qdrant"
                and vector_host
                and self.embeddings
            ):
                # Import LangChain Qdrant
                from langchain_qdrant import QdrantVectorStore
                from qdrant_client import QdrantClient

                # Build Qdrant URL
                qdrant_url = f"http://{vector_host}:{vector_port}"

                client = QdrantClient(
                    url=qdrant_url,
                    api_key=vector_api_key if vector_api_key else None,
                )

                self.vector_store = QdrantVectorStore(
                    client=client,
                    collection_name=vector_collection,
                    embedding=self.embeddings,
                )
                logger.info(
                    f"Initialized vector store: {vector_collection} at {qdrant_url}"
                )
            elif vector_provider != "qdrant":
                logger.info(
                    f"Vector provider '{vector_provider}' not supported by this tool (only 'qdrant')"
                )
            elif not vector_host:
                logger.warning("VECTOR_HOST not set - internal search unavailable")

        except Exception as e:
            logger.error(f"Failed to initialize internal search components: {e}")
            logger.info("Internal search tool will be unavailable")

    async def _arun(self, query: str, effort: str = "medium") -> str:
        """Execute internal search asynchronously.

        Args:
            query: Search query
            effort: Research depth level

        Returns:
            Formatted search results with citations
        """
        # Check if components are available
        if not all([self.vector_store, self.llm, self.embeddings]):
            return (
                "Internal search service not available (vector database not configured)"
            )

        try:
            logger.info(f"🔍 Internal search ({effort}): {query[:100]}...")

            # Determine number of sub-queries based on effort
            num_queries = {"low": 2, "medium": 3, "high": 5}.get(effort, 3)

            # Step 1: Decompose query into sub-queries
            sub_queries = await self._decompose_query(query, num_queries)
            logger.info(f"📋 Generated {len(sub_queries)} sub-queries")

            # Step 2: Retrieve context for each sub-query (with query rewriting)
            all_docs = []
            seen_content = set()

            for idx, sub_query in enumerate(sub_queries, 1):
                logger.debug(f"Retrieving for sub-query {idx}/{len(sub_queries)}")

                # Step 2a: Rewrite sub-query for better retrieval
                rewritten_query = await self._rewrite_query(sub_query, query)
                logger.debug(f"Rewritten query: {rewritten_query[:100]}...")

                # Use LangChain's similarity_search_with_score with rewritten query
                results = await self.vector_store.asimilarity_search_with_score(
                    rewritten_query,
                    k=5,  # Get top 5 per sub-query
                )

                # Deduplicate by content
                for doc, score in results:
                    content_key = doc.page_content[:100]  # First 100 chars as key
                    if content_key not in seen_content:
                        seen_content.add(content_key)
                        all_docs.append(
                            {
                                "content": doc.page_content,
                                "metadata": doc.metadata,
                                "score": score,
                                "sub_query": sub_query,
                            }
                        )

            # Step 3: Rank and limit
            all_docs.sort(key=lambda x: x["score"])  # Lower score = better in Qdrant
            max_docs = {"low": 8, "medium": 12, "high": 20}.get(effort, 12)
            final_docs = all_docs[:max_docs]

            logger.info(f"📊 Found {len(final_docs)} unique documents")

            # Step 4: Synthesize findings
            if not final_docs:
                return "**No relevant information found in internal knowledge base.**"

            summary = await self._synthesize_findings(query, final_docs, sub_queries)

            # Step 5: Format results
            result_text = self._format_results(
                summary, final_docs, sub_queries, len(all_docs)
            )

            return result_text

        except Exception as e:
            logger.error(f"Internal search failed: {e}", exc_info=True)
            return f"Internal search error: {str(e)}"

    def _run(self, query: str, effort: str = "medium") -> str:
        """Sync wrapper - not implemented (use async version)."""
        return "Internal search requires async execution. Use ainvoke() instead."

    async def _rewrite_query(self, sub_query: str, original_query: str) -> str:
        """Rewrite a sub-query to maximize retrieval from internal knowledge base.

        Transforms queries into search-optimized versions focused on internal
        information like past projects, clients, engagements, and documentation.

        Args:
            sub_query: The sub-query to rewrite
            original_query: Original user query for context

        Returns:
            Rewritten query optimized for internal knowledge retrieval
        """
        try:
            prompt = f"""You are optimizing search queries for an INTERNAL knowledge base containing:
- Past client projects and engagements
- Historical project documentation
- Internal company information
- Previous work examples and case studies

Original context: "{original_query}"
Sub-query to rewrite: "{sub_query}"

Rewrite the sub-query to:
1. Be specific to INTERNAL information (past projects, clients, our work)
2. Use language that matches internal documentation style
3. Include relevant context (client names, project types, timeframes if mentioned)
4. Focus on "what did we do" rather than "what should we do"
5. Keep it concise (1-2 sentences max)

Return ONLY the rewritten query, no explanation.

Examples:
Input: "similar clients"
Output: "What past clients or projects have we worked with that are similar in industry, size, or technical challenges?"

Input: "React projects"
Output: "What projects have we completed that used React, and what were the specific implementations or patterns we used?"

Input: "API work for fintech"
Output: "What API development or integration work have we done for financial technology clients or projects?"

Input: "agile transformations"
Output: "What past engagements involved helping clients adopt agile methodologies, and what were the outcomes?"

Now rewrite: "{sub_query}"
"""

            response = await self.llm.ainvoke(prompt)
            rewritten = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Fallback to original if rewriting fails or returns empty
            return rewritten.strip() if rewritten.strip() else sub_query

        except Exception as e:
            logger.debug(f"Query rewriting failed, using original: {e}")
            return sub_query

    async def _decompose_query(self, query: str, num_queries: int) -> list[str]:
        """Decompose complex query into focused sub-queries using LLM.

        Args:
            query: Original query
            num_queries: Number of sub-queries to generate

        Returns:
            List of sub-queries
        """
        prompt = f"""You are a research query planner. Break down this complex research query into {num_queries} DIVERSE sub-queries that will help retrieve comprehensive information from an internal knowledge base.

Original Query: "{query}"

Generate {num_queries} DISTINCT sub-queries that:
1. **Each query must explore a DIFFERENT aspect or angle** of the main query
2. **Vary the terminology and phrasing** - don't repeat the same words across queries
3. **Target different information types**: concepts, definitions, examples, use cases, comparisons, etc.
4. Are specific enough to retrieve relevant documents
5. Together provide comprehensive coverage of the topic

IMPORTANT: Each sub-query should be SUBSTANTIALLY DIFFERENT from the others.

Format your response as a JSON array of strings:
["sub-query 1", "sub-query 2", ..., "sub-query {num_queries}"]

Return ONLY the JSON array, no explanation."""

        try:
            response = await self.llm.ainvoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )

            sub_queries = json.loads(content.strip())

            if isinstance(sub_queries, list) and len(sub_queries) > 0:
                return sub_queries
            else:
                logger.warning(f"Invalid sub-query format, using original: {content}")
                return [query]

        except json.JSONDecodeError:
            logger.warning("Failed to parse sub-queries, using original")
            return [query]
        except Exception as e:
            logger.error(f"Query decomposition failed: {e}")
            return [query]

    async def _synthesize_findings(
        self, query: str, docs: list[dict], sub_queries: list[str]
    ) -> str:
        """Synthesize findings into a summary using LLM.

        Args:
            query: Original query
            docs: Retrieved documents
            sub_queries: Sub-queries used

        Returns:
            Synthesized summary
        """
        if not docs:
            return "No relevant information found."

        # Build context from top documents
        context_parts = []
        for idx, doc in enumerate(docs[:8], 1):
            file_name = doc.get("metadata", {}).get("file_name", "unknown")
            content = doc.get("content", "")[:400]
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

        try:
            response = await self.llm.ainvoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )
            return content or "Unable to synthesize findings."
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return "Error synthesizing findings."

    def _format_results(
        self,
        summary: str,
        docs: list[dict],
        sub_queries: list[str],
        total_retrieved: int,
    ) -> str:
        """Format search results for presentation.

        Args:
            summary: Synthesized summary
            docs: Final documents
            sub_queries: Sub-queries used
            total_retrieved: Total documents retrieved

        Returns:
            Formatted result string
        """
        result_text = f"# Internal Knowledge Base Search\n\n{summary}\n\n"

        # Add document citations
        unique_files = len(
            {doc.get("metadata", {}).get("file_name", "unknown") for doc in docs}
        )

        result_text += (
            f"**Found in {unique_files} internal documents ({len(docs)} sections):**\n"
        )

        # List unique documents with relevance scores
        files_seen = set()
        for doc in docs[:10]:
            file_name = doc.get("metadata", {}).get("file_name", "unknown")
            if file_name not in files_seen:
                files_seen.add(file_name)
                score = doc.get("score", 0)
                # Qdrant uses distance (lower is better), convert to similarity %
                similarity = max(0, 1 - score) * 100
                result_text += f"- {file_name} (relevance: {similarity:.0f}%)\n"

        result_text += f"\n**Search Strategy:** {len(sub_queries)} focused queries "
        result_text += f"(retrieved {total_retrieved} total sections)\n"

        # Add sources section with proper format for source detection
        # Format sources with "Internal search" keyword so they're detected by format_research_context
        result_text += "\n\n### Sources\n\n"
        files_seen = set()
        for doc in docs[:10]:
            file_name = doc.get("metadata", {}).get("file_name", "unknown")
            web_view_link = doc.get("metadata", {}).get(
                "web_view_link", "internal://knowledge-base"
            )
            if file_name not in files_seen:
                files_seen.add(file_name)
                # Use "Internal search" keyword so source gets tagged as [INTERNAL_KB]
                result_text += (
                    f"- {web_view_link} - Internal search result: {file_name}\n"
                )

        return result_text


# Factory function for easy instantiation
def internal_search_tool(
    vector_store: Any = None,
    llm: Any = None,
    embeddings: Any = None,
) -> InternalSearchTool | None:
    """Create an internal search tool instance.

    Args:
        vector_store: Optional LangChain VectorStore (will be lazy-loaded if not provided)
        llm: Optional LangChain ChatModel (will be lazy-loaded if not provided)
        embeddings: Optional LangChain Embeddings (will be lazy-loaded if not provided)

    Returns:
        Configured InternalSearchTool or None if unavailable
    """
    try:
        return InternalSearchTool(
            vector_store=vector_store,
            llm=llm,
            embeddings=embeddings,
        )
    except Exception as e:
        logger.error(f"Failed to create internal search tool: {e}")
        return None
