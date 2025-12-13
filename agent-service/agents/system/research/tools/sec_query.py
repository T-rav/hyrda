"""SEC Query Tool - On-demand SEC research with query rewriting.

Fetches and searches SEC filings on-demand from SEC Edgar API with no pre-indexing.
Uses multi-angle query rewriting for comprehensive search across 10-K and 8-K filings.
"""

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from ..services.sec_cache import SECFilingsCache
from ..services.sec_on_demand import SECOnDemandFetcher
from ..services.sec_vector_search import SECInMemoryVectorSearch

logger = logging.getLogger(__name__)


class SECQueryInput(BaseModel):
    """Input schema for SEC query tool."""

    query: str = Field(
        min_length=3,
        description="What to search for in SEC filings (10-K, 8-K). Be specific about company name and what you're looking for. MUST be a meaningful search query (minimum 3 characters). DO NOT call with empty string.",
    )
    effort: str = Field(
        default="medium",
        description='Research depth - "low" (2 queries), "medium" (3 queries), "high" (5 queries). Default: "medium"',
    )


class SECQueryTool(BaseTool):
    """Search SEC filings on-demand for company financial and strategic information.

    Fetches latest 10-K (annual report) and 4 most recent 8-Ks (material events)
    just-in-time, then searches for relevant information.

    Use this to find:
    - Risk factors and strategic challenges
    - Financial performance and trends
    - Strategic priorities and initiatives
    - Technology investments and R&D spending
    - Market position and competitive landscape
    - Executive commentary and forward-looking statements
    - Executive changes and leadership movements (8-K Item 5.02)
    - Key announcements and material events (8-K disclosures)
    - Acquisitions, partnerships, and corporate actions

    No pre-indexing required - fetches documents on-demand from SEC Edgar API.
    """

    name: str = "sec_query"
    description: str = (
        "Search SEC filings on-demand (10-K annual reports, 8-K current events) for company information. "
        "Fetches latest filings from SEC Edgar API and searches for relevant information. "
        "Find risk factors, strategic priorities, financial data, R&D investments, executive commentary, "
        "executive changes, leadership movements, key announcements, material events, acquisitions, and partnerships. "
        "IMPORTANT: Must include company name or ticker in query. Only call with specific search query (minimum 3 characters). "
        "DO NOT call with empty query."
    )
    args_schema: type[BaseModel] = SECQueryInput

    # LangChain LLM for query rewriting
    llm: Any = None
    openai_api_key: str | None = None

    class Config:
        """Config class."""

        arbitrary_types_allowed = True

    def __init__(self, llm: Any = None, openai_api_key: str | None = None, **kwargs):
        """Initialize with LangChain LLM for query rewriting.

        Args:
            llm: LangChain ChatModel for query rewriting
            openai_api_key: OpenAI API key for embeddings
            **kwargs: Additional BaseTool arguments
        """
        kwargs["llm"] = llm
        kwargs["openai_api_key"] = openai_api_key
        super().__init__(**kwargs)

        if not self.llm:
            self._initialize_llm()

        if not self.openai_api_key:
            import os

            self.openai_api_key = os.getenv("LLM_API_KEY") or os.getenv(
                "OPENAI_API_KEY"
            )

    def _initialize_llm(self):
        """Initialize LLM from environment (fallback)."""
        try:
            import os

            from langchain_openai import ChatOpenAI

            llm_api_key = os.getenv("LLM_API_KEY")
            llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")

            self.llm = ChatOpenAI(
                model=llm_model,
                api_key=llm_api_key,
                temperature=0,
            )
            logger.info(f"Initialized LLM: {llm_model}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise

    def _run(self, query: str, effort: str = "medium") -> str:
        """Synchronous run (not supported)."""
        raise NotImplementedError("Use async _arun method")

    async def _arun(self, query: str, effort: str = "medium") -> str:
        """Execute on-demand SEC query with multi-angle search.

        Args:
            query: Search query (should include company name/ticker)
            effort: Research depth level

        Returns:
            Formatted search results with sources
        """
        try:
            # Validate query
            if not query or len(query) < 3:
                return "Error: Query must be at least 3 characters. Please provide a specific company name and what you're looking for."

            logger.info(f"SEC query: {query} (effort: {effort})")

            # Extract company identifier (ticker or name)
            company_identifier = self._extract_company_identifier(query)
            if not company_identifier:
                return "Error: Could not identify company name or ticker in query. Please include company name (e.g., 'Apple') or ticker (e.g., 'AAPL')."

            logger.info(f"Identified company: {company_identifier}")

            # Determine number of sub-queries based on effort
            effort_map = {"low": 2, "medium": 3, "high": 5}
            num_queries = effort_map.get(effort, 3)

            # Generate sub-queries for multi-angle search
            sub_queries = await self._generate_sub_queries(query, num_queries)
            logger.info(f"Generated {len(sub_queries)} sub-queries")

            # Initialize cache and vector search
            import os

            redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
            cache = SECFilingsCache(redis_url=redis_url)
            vector_search = SECInMemoryVectorSearch(self.openai_api_key)

            # Step 1: Check cache first
            cached_data = await cache.get_cached_filings(company_identifier)

            if cached_data:
                # Cache hit - load from cache
                logger.info(
                    f"💨 Cache hit for {company_identifier} "
                    f"({cached_data['total_chunks']} chunks)"
                )

                # Load embeddings from cache
                if "embeddings" in cached_data:
                    vector_search.load_from_cache(
                        cached_data["chunks"],
                        cached_data["chunk_metadata"],
                        cached_data["embeddings"],
                    )
                else:
                    # Old cache format without embeddings - regenerate
                    logger.warning(
                        "Cache data missing embeddings, regenerating... "
                        "(consider clearing old cache)"
                    )
                    # Group chunks by filing metadata to ensure correct chunk_index calculation
                    # Process all chunks from the same filing together
                    filing_groups: dict[tuple, list[tuple[str, dict]]] = {}
                    for chunk, metadata in zip(
                        cached_data["chunks"],
                        cached_data["chunk_metadata"],
                        strict=False,
                    ):
                        # Create a key from filing-level metadata (excluding chunk_index)
                        filing_key = (
                            metadata.get("type"),
                            metadata.get("date"),
                            metadata.get("url"),
                            metadata.get("accession"),
                        )
                        if filing_key not in filing_groups:
                            filing_groups[filing_key] = []
                        filing_groups[filing_key].append((chunk, metadata))

                    # Process each filing group together
                    for _filing_key, chunk_list in filing_groups.items():
                        chunks = [chunk for chunk, _ in chunk_list]
                        # Use first chunk's metadata as base (chunk_index will be recalculated)
                        base_metadata = chunk_list[0][1].copy()
                        # Remove chunk_index if present - it will be recalculated correctly
                        base_metadata.pop("chunk_index", None)
                        await vector_search.add_filing_chunks(chunks, base_metadata)

                company_name = cached_data["company_name"]
                filings = cached_data["filings"]

            else:
                # Cache miss - fetch and process
                logger.info(
                    f"Cache miss for {company_identifier}, fetching from SEC..."
                )

                # Fetch SEC documents on-demand
                fetcher = SECOnDemandFetcher()
                try:
                    filing_data = await fetcher.get_company_filings_for_research(
                        company_identifier
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch SEC filings: {e}")
                    return f"Error: Could not fetch SEC filings for {company_identifier}. Company may not be public or ticker/CIK not found."

                company_name = filing_data["company_name"]
                filings = filing_data["filings"]

                logger.info(
                    f"✅ Fetched {len(filings)} filings for {company_name} "
                    f"({filing_data['total_characters']:,} characters)"
                )

                # Chunk and vectorize in-memory
                all_chunks = []
                all_chunk_metadata = []

                for filing in filings:
                    chunks = fetcher.chunk_filing_content(filing["content"])
                    filing_metadata = {
                        "type": filing["type"],
                        "date": filing["date"],
                        "url": filing["url"],
                        "accession": filing["accession_number"],
                        "company_name": company_name,
                    }

                    await vector_search.add_filing_chunks(chunks, filing_metadata)

                    # Track for caching
                    all_chunks.extend(chunks)
                    all_chunk_metadata.extend(
                        [filing_metadata.copy() for _ in range(len(chunks))]
                    )

                # Cache the results
                embeddings_array = vector_search.get_embeddings_array()
                await cache.cache_filings(
                    company_identifier=company_identifier,
                    company_name=company_name,
                    filings=filings,
                    chunks=all_chunks,
                    chunk_metadata=all_chunk_metadata,
                    embeddings=embeddings_array,
                )

            # Step 3: Search across all sub-queries
            all_results = []
            seen_content = set()

            for idx, sub_query in enumerate(sub_queries, 1):
                logger.debug(f"Searching sub-query {idx}/{len(sub_queries)}")

                # Rewrite query for SEC filing optimization
                rewritten = await self._rewrite_query_for_sec(sub_query, query)
                logger.debug(f"Rewritten: {rewritten}")

                # Search in-memory index
                results = await vector_search.search(rewritten, top_k=20, min_score=0.5)

                logger.info(
                    f"   Sub-query '{sub_query}' returned {len(results)} results"
                )

                # Deduplicate by content
                for result in results:
                    content_key = result["content"][:100]
                    if content_key not in seen_content:
                        seen_content.add(content_key)
                        all_results.append(
                            {
                                "content": result["content"],
                                "metadata": result["metadata"],
                                "score": result["score"],
                                "sub_query": sub_query,
                            }
                        )

            # Clean up memory
            vector_search.clear()

            if not all_results:
                return f"No relevant information found in {company_name}'s SEC filings for: {query}"

            # Sort by relevance score
            all_results.sort(key=lambda x: x["score"], reverse=True)

            # Take top results
            top_results = all_results[:15]

            # Format results
            formatted = self._format_results(top_results, query, company_name, filings)

            logger.info(f"Returned {len(top_results)} SEC filing results")
            return formatted

        except Exception as e:
            logger.error(f"SEC query failed: {e}", exc_info=True)
            return f"Error querying SEC filings: {str(e)}"

    def _extract_company_identifier(self, query: str) -> str | None:
        """Extract company name or ticker from query.

        Returns first capitalized word or known ticker pattern.
        """
        import re

        words = query.split()

        # Check for ticker pattern (2-5 uppercase letters)
        for word in words:
            clean = re.sub(r"[^\w]", "", word)
            if clean.isupper() and 2 <= len(clean) <= 5:
                return clean

        # Check for capitalized words (potential company name)
        for word in words:
            clean = re.sub(r"[^\w]", "", word)
            if len(clean) > 3 and clean[0].isupper():
                return clean

        return None

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
7. Executive changes and leadership movements
8. Key announcements and material events
9. Acquisitions, partnerships, and corporate actions

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

            prompt = f"""You are optimizing search queries for SEC FILINGS (10-K, 8-K) which contain:
- Risk factors and strategic challenges
- Management discussion & analysis (MD&A)
- Financial performance and trends
- Forward-looking statements
- Technology and R&D investments
- Market position and competitive landscape
- Executive changes and leadership movements (Item 5.02 in 8-Ks)
- Key announcements and material events (8-K disclosures)
- Acquisitions, partnerships, and corporate actions

Original context: "{original_query}"
Sub-query to rewrite: "{sub_query}"

**CRITICAL: If a company name is mentioned (like "{company_name}"), you MUST include it in the rewritten query.**

Rewrite the sub-query to:
1. **ALWAYS include the company name if present in the original context**
2. Use language that matches SEC filing terminology (risk factors, MD&A, strategic priorities, Item 5.02, material events, etc.)
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

Input original: "Salesforce leadership", sub-query: "executive changes"
Output: "What executive appointments, departures, or leadership changes has Salesforce disclosed in 8-K Item 5.02 filings?"

Input original: "Meta announcements", sub-query: "material events"
Output: "What material events, acquisitions, or strategic announcements has Meta disclosed in recent 8-K filings?"

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

    def _format_results(
        self, results: list[dict], query: str, company_name: str, filings: list[dict]
    ) -> str:
        """Format search results with source attribution."""
        output = f"## SEC Filing Results for {company_name}: {query}\n\n"
        output += f"Searched {len(filings)} filings:\n"
        for filing in filings:
            output += f"  • {filing['type']} ({filing['date']})\n"
        output += f"\nFound {len(results)} relevant sections:\n\n"

        # Group by filing
        by_filing = {}
        for result in results:
            metadata = result["metadata"]
            filing_key = (
                f"{metadata.get('type', 'Unknown')} - {metadata.get('date', 'Unknown')}"
            )

            if filing_key not in by_filing:
                by_filing[filing_key] = []

            by_filing[filing_key].append(result)

        # Format grouped results
        for filing_key, docs in list(by_filing.items())[:5]:  # Top 5 filings
            output += f"### {filing_key}\n"

            metadata = docs[0]["metadata"]
            if "url" in metadata:
                output += f"Source: {metadata['url']}\n\n"

            # Show top 2 chunks per filing
            for doc in docs[:2]:
                content = doc["content"]
                # Truncate long content
                if len(content) > 800:
                    content = content[:800] + "..."

                output += f"{content}\n\n"

            output += "---\n\n"

        return output
