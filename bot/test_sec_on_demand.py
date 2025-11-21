"""Test script for on-demand SEC fetching."""

import asyncio
import logging
import os

from agents.profiler.tools.sec_research import (
    format_sec_research_results,
    research_sec_filings,
)

logging.basicConfig(level=logging.INFO)


async def main():
    """Test SEC on-demand fetching."""
    # Test with Apple (AAPL)
    company = "AAPL"
    query = "What are the company's main revenue sources and business segments?"

    openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not openai_key:
        print("❌ OPENAI_API_KEY or LLM_API_KEY environment variable required")
        return

    print(f"\n{'=' * 60}")
    print("Testing SEC On-Demand Research")
    print(f"{'=' * 60}\n")
    print(f"Company: {company}")
    print(f"Query: {query}\n")

    # Run research
    results = await research_sec_filings(company, query, openai_key, top_k=3)

    # Format and print results
    formatted = format_sec_research_results(results)
    print(formatted)

    print(f"\n{'=' * 60}")
    print("Test Complete")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
