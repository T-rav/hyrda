"""SEC Research Tool for Profile Agent

On-demand SEC document fetching and search for deep company research.
No persistence - all processing happens in-memory.
"""

import logging
from typing import Any

from agents.profiler.services.sec_on_demand import SECOnDemandFetcher
from agents.profiler.services.sec_vector_search import SECInMemoryVectorSearch

logger = logging.getLogger(__name__)


async def research_sec_filings(
    company_identifier: str,
    research_query: str,
    openai_api_key: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Research SEC filings for a company on-demand.

    Fetches latest 10-K and 4 most recent 8-Ks, vectorizes in-memory,
    and searches for relevant information.

    Args:
        company_identifier: Ticker symbol or CIK
        research_query: What to search for in the filings
        openai_api_key: OpenAI API key for embeddings
        top_k: Number of relevant chunks to return

    Returns:
        Dictionary with relevant excerpts from SEC filings

    """
    logger.info(f"Researching SEC filings for {company_identifier}")
    logger.info(f"Query: {research_query}")

    # Step 1: Fetch SEC documents
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

    # Step 2: Chunk and vectorize in-memory
    vector_search = SECInMemoryVectorSearch(openai_api_key)

    for filing in filings:
        chunks = fetcher.chunk_filing_content(filing["content"])

        filing_metadata = {
            "type": filing["type"],
            "date": filing["date"],
            "url": filing["url"],
            "accession": filing["accession_number"],
        }

        await vector_search.add_filing_chunks(chunks, filing_metadata)

    index_stats = vector_search.get_stats()
    logger.info(
        f"✅ Vectorized {index_stats['total_chunks']} chunks "
        f"({index_stats['total_characters']:,} characters)"
    )

    # Step 3: Search for relevant information
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
