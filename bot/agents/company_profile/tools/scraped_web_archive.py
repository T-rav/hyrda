"""Scraped Web Archive search tool for querying SEC filings.

Searches SEC 10-K, 10-Q, and 8-K filings in the vector database
using query rewriting for optimal retrieval.
"""

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ScrapedWebArchiveInput(BaseModel):
    """Input schema for scraped web archive search tool."""

    query: str = Field(
        min_length=3,
        description="What to search for in SEC filings (10-K, 10-Q, 8-K). Be specific about company name and what you're looking for. MUST be a meaningful search query (minimum 3 characters). DO NOT call with empty string.",
    )
    effort: str = Field(
        default="medium",
        description='Research depth - "low" (2 queries), "medium" (3 queries), "high" (5 queries). Default: "medium"',
    )


class ScrapedWebArchiveTool(BaseTool):
    """Search scraped web archive (SEC filings: 10-K, 10-Q, 8-K) for company financial and strategic information.

    Use this to find:
    - Risk factors and strategic challenges
    - Financial performance and trends
    - Strategic priorities and initiatives
    - Technology investments and R&D spending
    - Market position and competitive landscape
    - Executive commentary and forward-looking statements

    This tool searches ingested SEC Edgar filings in the vector database.
    """

    name: str = "scraped_web_archive"
    description: str = (
        "Search scraped web archive (SEC filings: 10-K annual reports, 10-Q quarterly reports, 8-K current events) for company information. "
        "Find risk factors, strategic priorities, financial data, R&D investments, and executive commentary from official SEC filings. "
        "IMPORTANT: Must include company name in query. Only call with specific search query (minimum 3 characters). "
        "DO NOT call with empty query."
    )
    args_schema: type[BaseModel] = ScrapedWebArchiveInput

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
            vector_store: LangChain VectorStore instance
            llm: LangChain ChatModel for query rewriting
            embeddings: LangChain Embeddings
            **kwargs: Additional BaseTool arguments
        """
        kwargs["vector_store"] = vector_store
        kwargs["llm"] = llm
        kwargs["embeddings"] = embeddings

        super().__init__(**kwargs)

        if not all([self.vector_store, self.llm, self.embeddings]):
            self._initialize_components()

    def _initialize_components(self):
        """Initialize LangChain components from environment (fallback only)."""
        try:
            import os

            # Get settings from environment
            llm_api_key = os.getenv("LLM_API_KEY")
            llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")

            embedding_api_key = os.getenv("EMBEDDING_API_KEY", llm_api_key)
            embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            qdrant_api_key = os.getenv("QDRANT_API_KEY")
            collection_name = os.getenv(
                "QDRANT_COLLECTION_NAME", "insightmesh-knowledge-base"
            )

            # Initialize LLM
            if not self.llm:
                from langchain_openai import ChatOpenAI

                self.llm = ChatOpenAI(
                    model=llm_model,
                    api_key=llm_api_key,
                    temperature=0,
                )
                logger.info(f"Initialized LLM: {llm_model}")

            # Initialize embeddings
            if not self.embeddings:
                from langchain_openai import OpenAIEmbeddings

                self.embeddings = OpenAIEmbeddings(
                    model=embedding_model,
                    api_key=embedding_api_key,
                )
                logger.info(f"Initialized embeddings: {embedding_model}")

            # Initialize vector store
            if not self.vector_store:
                from langchain_qdrant import QdrantVectorStore
                from qdrant_client import QdrantClient

                qdrant_client = QdrantClient(
                    url=qdrant_url,
                    api_key=qdrant_api_key,
                    timeout=60,
                )

                self.vector_store = QdrantVectorStore(
                    client=qdrant_client,
                    collection_name=collection_name,
                    embedding=self.embeddings,
                )
                logger.info(f"Initialized Qdrant: {collection_name}")

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise

    def _run(self, query: str, effort: str = "medium") -> str:
        """Synchronous run (not supported)."""
        raise NotImplementedError("Use async _arun method")

    async def _arun(self, query: str, effort: str = "medium") -> str:
        """Execute scraped web archive search on SEC filings.

        Args:
            query: Search query (should include company name)
            effort: Research depth level

        Returns:
            Formatted search results with sources
        """
        try:
            # Validate query
            if not query or len(query) < 3:
                return "Error: Query must be at least 3 characters. Please provide a specific company name and what you're looking for."

            logger.info(f"Scraped web archive search: {query} (effort: {effort})")

            # Determine number of sub-queries based on effort
            effort_map = {"low": 2, "medium": 3, "high": 5}
            num_queries = effort_map.get(effort, 3)

            # Generate sub-queries for multi-angle search
            sub_queries = await self._generate_sub_queries(query, num_queries)
            logger.info(f"Generated {len(sub_queries)} sub-queries")

            # Search across all sub-queries
            all_docs = []
            seen_content = set()

            for idx, sub_query in enumerate(sub_queries, 1):
                logger.debug(f"Searching sub-query {idx}/{len(sub_queries)}")

                # Rewrite query for SEC filing optimization
                rewritten = await self._rewrite_query_for_sec(sub_query, query)
                logger.debug(f"Rewritten: {rewritten}")

                # Search with SEC source filter
                results = await self.vector_store.asimilarity_search_with_score(
                    rewritten,
                    k=30,  # Get more results for better coverage
                    filter={"source": "sec_edgar"},  # Only SEC filings
                    score_threshold=None,
                )

                logger.info(
                    f"   Sub-query '{sub_query}' returned {len(results)} SEC filing results"
                )

                # Apply entity boosting
                results = self._apply_entity_boosting(query, results)

                # Deduplicate by content
                for doc, score in results:
                    content_key = doc.page_content[:100]
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

            if not all_docs:
                return f"No SEC filings found for: {query}\n\nThis may mean:\n- Company is not public (no SEC filings)\n- Filings not yet ingested\n- Company name spelling differs"

            # Sort by relevance score
            all_docs.sort(key=lambda x: x["score"], reverse=True)

            # Take top results
            top_results = all_docs[:15]

            # Format results
            formatted = self._format_results(top_results, query)

            logger.info(f"Returned {len(top_results)} SEC filing results")
            return formatted

        except Exception as e:
            logger.error(f"Scraped web archive search failed: {e}", exc_info=True)
            return f"Error searching SEC filings: {str(e)}"

    async def _generate_sub_queries(self, query: str, num_queries: int) -> list[str]:
        """Generate multiple sub-queries for comprehensive SEC filing search."""
        try:
            prompt = f"""Generate {num_queries} diverse search queries to comprehensively research SEC filings for: "{query}"

Focus on different aspects typically found in SEC filings:
1. Risk factors and challenges
2. Strategic priorities and initiatives
3. Financial performance and metrics
4. Technology and R&D investments
5. Market position and competition
6. Regulatory and compliance matters

Return as JSON array of strings: ["query1", "query2", "query3"]
"""

            response = await self.llm.ainvoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Parse JSON response
            queries = json.loads(content)

            # Fallback if parsing fails
            if not isinstance(queries, list) or len(queries) == 0:
                return [query]

            return queries[:num_queries]

        except Exception as e:
            logger.warning(f"Failed to generate sub-queries: {e}")
            return [query]  # Fallback to original query

    async def _rewrite_query_for_sec(self, sub_query: str, original_query: str) -> str:
        """Rewrite query to maximize retrieval from SEC filings.

        Transforms queries into search-optimized versions focused on SEC filing language
        like risk factors, strategic initiatives, financial performance, etc.
        """
        try:
            # Extract company name from original query (simple pattern)
            words = original_query.split()
            company_name = None
            for word in words:
                if len(word) > 3 and word[0].isupper():
                    company_name = word
                    break

            prompt = f"""You are optimizing search queries for SEC FILINGS (10-K, 10-Q, 8-K) which contain:
- Risk factors and strategic challenges
- Management discussion & analysis (MD&A)
- Financial performance and trends
- Forward-looking statements
- Technology and R&D investments
- Market position and competitive landscape

Original context: "{original_query}"
Sub-query to rewrite: "{sub_query}"

**CRITICAL: If a company name is mentioned (like "{company_name}"), you MUST include it in the rewritten query.**

Rewrite the sub-query to:
1. **ALWAYS include the company name if present in the original context**
2. Use language that matches SEC filing terminology (risk factors, MD&A, strategic priorities, etc.)
3. Focus on specific SEC sections that would contain this information
4. Be specific about what type of information you're looking for
5. Keep it concise (1-2 sentences max)

Return ONLY the rewritten query, no explanation.

Examples:
Input original: "Apple strategic priorities", sub-query: "product strategy"
Output: "What are Apple's key product development priorities and roadmap mentioned in their 10-K MD&A section?"

Input original: "Microsoft risks", sub-query: "competitive threats"
Output: "What competitive risks and market challenges does Microsoft identify in their 10-K risk factors section?"

Input original: "Tesla R&D", sub-query: "technology investments"
Output: "What are Tesla's R&D investments and technology development priorities disclosed in SEC filings?"

Now rewrite: "{sub_query}"
"""

            response = await self.llm.ainvoke(prompt)
            rewritten = (
                response.content if hasattr(response, "content") else str(response)
            )

            return rewritten.strip() if rewritten.strip() else sub_query

        except Exception as e:
            logger.debug(f"Query rewrite failed, using original: {e}")
            return sub_query

    def _extract_entities_simple(self, query: str) -> set[str]:
        """Extract company names and key entities from query."""
        import re

        entities = set()

        # Extract capitalized words (potential company names)
        words = query.split()
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r"[^\w\s]", "", word)
            if len(clean_word) > 2 and clean_word[0].isupper():
                entities.add(clean_word.lower())

        return entities

    def _apply_entity_boosting(self, query: str, results: list[tuple]) -> list[tuple]:
        """Boost results that mention key entities from the query."""
        entities = self._extract_entities_simple(query)

        if not entities:
            return results

        boosted_results = []
        for doc, score in results:
            # Check if document mentions any key entities
            doc_text_lower = doc.page_content.lower()
            doc_metadata_lower = json.dumps(doc.metadata).lower()

            boost = 1.0
            for entity in entities:
                if entity in doc_text_lower or entity in doc_metadata_lower:
                    boost *= 1.3  # 30% boost per entity match

            boosted_score = score * boost
            boosted_results.append((doc, boosted_score))

        # Re-sort by boosted score
        boosted_results.sort(key=lambda x: x[1], reverse=True)
        return boosted_results

    def _format_results(self, results: list[dict], query: str) -> str:
        """Format search results with source attribution."""
        output = f"## SEC Filing Results for: {query}\n\n"
        output += f"Found {len(results)} relevant sections from SEC filings:\n\n"

        # Group by company and filing
        by_filing = {}
        for result in results:
            metadata = result["metadata"]
            filing_key = f"{metadata.get('company_name', 'Unknown')} - {metadata.get('filing_type', 'Unknown')} - {metadata.get('filing_date', 'Unknown')}"

            if filing_key not in by_filing:
                by_filing[filing_key] = []

            by_filing[filing_key].append(result)

        # Format grouped results
        for filing_key, docs in list(by_filing.items())[:5]:  # Top 5 filings
            output += f"### {filing_key}\n"

            metadata = docs[0]["metadata"]
            if "document_url" in metadata:
                output += f"Source: {metadata['document_url']}\n\n"

            # Show top 2 chunks per filing
            for doc in docs[:2]:
                content = doc["content"]
                # Truncate long content
                if len(content) > 800:
                    content = content[:800] + "..."

                output += f"{content}\n\n"

            output += "---\n\n"

        return output
