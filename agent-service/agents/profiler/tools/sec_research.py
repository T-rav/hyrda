"""SEC Research Tool for Profile Agent

On-demand SEC document fetching and search for deep company research.
Includes optional Redis caching to avoid re-fetching and re-embedding.
"""

import logging
from typing import Any

from agents.profiler.services.sec_cache import SECFilingsCache
from agents.profiler.services.sec_on_demand import SECOnDemandFetcher
from agents.profiler.services.sec_vector_search import SECInMemoryVectorSearch

logger = logging.getLogger(__name__)


async def research_sec_filings(
    company_identifier: str,
    research_query: str,
    openai_api_key: str,
    top_k: int = 5,
    redis_url: str = "redis://localhost:6379",
    cache_enabled: bool = True,
) -> dict[str, Any]:
    """
    Research SEC filings for a company on-demand with optional caching.

    Fetches latest 10-K and 4 most recent 8-Ks, vectorizes in-memory,
    and searches for relevant information. Caches filings and embeddings
    for 1 hour to avoid re-fetching when multiple researchers query same company.

    Args:
        company_identifier: Ticker symbol or CIK
        research_query: What to search for in the filings
        openai_api_key: OpenAI API key for embeddings
        top_k: Number of relevant chunks to return
        redis_url: Redis connection URL (default: redis://localhost:6379)
        cache_enabled: Enable/disable caching (default: True)

    Returns:
        Dictionary with relevant excerpts from SEC filings
    """
    logger.info(f"Researching SEC filings for {company_identifier}")
    logger.info(f"Query: {research_query}")

    # Initialize cache
    cache = SECFilingsCache(redis_url=redis_url) if cache_enabled else None
    vector_search = SECInMemoryVectorSearch(openai_api_key)

    # Step 1: Check cache first
    cached_data = None
    if cache:
        cached_data = await cache.get_cached_filings(company_identifier)

    if cached_data:
        # Cache hit - load from cache
        logger.info(
            f"💨 Cache hit for {company_identifier} "
            f"({cached_data['total_chunks']} chunks, "
            f"{cached_data['total_characters']:,} characters)"
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
                cached_data["chunks"], cached_data["chunk_metadata"]
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
            for filing_key, chunk_list in filing_groups.items():
                chunks = [chunk for chunk, _ in chunk_list]
                # Use first chunk's metadata as base (chunk_index will be recalculated)
                base_metadata = chunk_list[0][1].copy()
                # Remove chunk_index if present - it will be recalculated correctly
                base_metadata.pop("chunk_index", None)
                await vector_search.add_filing_chunks(chunks, base_metadata)

        company_name = cached_data["company_name"]
        filings = cached_data["filings"]
        index_stats = {
            "total_chunks": cached_data["total_chunks"],
            "total_characters": cached_data["total_characters"],
            "filings": [f["type"] for f in filings],
        }

    else:
        # Cache miss - fetch and process
        logger.info(f"Cache miss for {company_identifier}, fetching from SEC...")

        # Fetch SEC documents
        fetcher = SECOnDemandFetcher()
        try:
            filing_data = await fetcher.get_company_filings_for_research(
                company_identifier, research_query
            )
        except Exception as e:
            logger.error(f"Failed to fetch SEC filings: {e}")
            return {
                "success": False,
                "error": str(e),
                "company_identifier": company_identifier,
            }

        company_name = filing_data["company_name"]
        filings = filing_data["filings"]

        logger.info(
            f"✅ Fetched {len(filings)} filings for {company_name} "
            f"({filing_data['total_characters']:,} characters)"
        )

        # Chunk and vectorize
        all_chunks = []
        all_chunk_metadata = []

        for filing in filings:
            chunks = fetcher.chunk_filing_content(filing["content"])

            filing_metadata = {
                "type": filing["type"],
                "date": filing["date"],
                "url": filing["url"],
                "accession": filing["accession_number"],
            }

            # Add to vector search
            await vector_search.add_filing_chunks(chunks, filing_metadata)

            # Track for caching
            all_chunks.extend(chunks)
            all_chunk_metadata.extend([filing_metadata.copy() for _ in range(len(chunks))])

        index_stats = vector_search.get_stats()
        logger.info(
            f"✅ Vectorized {index_stats['total_chunks']} chunks "
            f"({index_stats['total_characters']:,} characters)"
        )

        # Cache the results
        if cache:
            embeddings_array = vector_search.get_embeddings_array()
            await cache.cache_filings(
                company_identifier=company_identifier,
                company_name=company_name,
                filings=filings,
                chunks=all_chunks,
                chunk_metadata=all_chunk_metadata,
                embeddings=embeddings_array,
            )

    # Step 2: Search for relevant information (works for both cached and fresh data)
    results = await vector_search.search(research_query, top_k=top_k)

    logger.info(f"✅ Found {len(results)} relevant excerpts")

    # Clean up memory
    vector_search.clear()

    return {
        "success": True,
        "company_name": company_name,
        "company_identifier": company_identifier,
        "query": research_query,
        "filings_searched": [
            {"type": f["type"], "date": f["date"], "url": f["url"]} for f in filings
        ],
        "relevant_excerpts": results,
        "total_excerpts": len(results),
        "index_stats": index_stats,
        "cache_hit": cached_data is not None,
    }


def format_sec_research_results(results: dict[str, Any]) -> str:
    """
    Format SEC research results for inclusion in LLM context.

    Args:
        results: Results from research_sec_filings

    Returns:
        Formatted string for LLM context
    """
    if not results.get("success"):
        return f"❌ SEC research failed: {results.get('error', 'Unknown error')}"

    output = []
    output.append(f"📊 SEC Filings Research: {results['company_name']}")
    output.append("")

    # List filings searched
    output.append(f"Searched {len(results['filings_searched'])} filings:")
    for filing in results["filings_searched"]:
        output.append(f"  • {filing['type']} ({filing['date']}): {filing['url']}")
    output.append("")

    # Show relevant excerpts
    output.append(f"Found {results['total_excerpts']} relevant excerpts:")
    output.append("")

    for i, excerpt in enumerate(results["relevant_excerpts"], 1):
        metadata = excerpt["metadata"]
        score = excerpt["score"]
        content = excerpt["content"]

        # Truncate very long excerpts
        if len(content) > 1000:
            content = content[:1000] + "..."

        output.append(
            f"Excerpt {i} (Score: {score:.2f}) - {metadata['type']} ({metadata['date']}):"
        )
        output.append(f"{content}")
        output.append("")

    return "\n".join(output)
