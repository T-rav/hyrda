"""Lightweight search service for custom agents.

Provides Tavily search client without depending on bot/services.
Includes MinIO caching for search results and scraped content.
"""

import logging
import os
from typing import Any

from profiler.services.tavily_cache import get_tavily_cache

logger = logging.getLogger(__name__)


def get_tavily_client():
    """Get Tavily client for web search."""
    api_key = os.getenv("TAVILY_API_KEY")
    logger.info(f"get_tavily_client called - API key: {'SET (' + api_key[:10] + '...)' if api_key else 'NOT SET'}")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set - search tools will not be available")
        return None

    try:
        from tavily import TavilyClient

        return TavilyClient(api_key=api_key)
    except ImportError:
        logger.error("tavily-python not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Tavily client: {e}")
        return None


def get_perplexity_client():
    """Get Perplexity client for deep research.

    Returns:
        dict with api_key if available, None otherwise
    """
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return None

    return {"api_key": api_key, "model": "llama-3.1-sonar-large-128k-online"}


async def cached_web_search(
    query: str, max_results: int = 10
) -> list[dict[str, Any]]:
    """Execute web search with MinIO caching.

    Args:
        query: Search query string
        max_results: Maximum number of results

    Returns:
        List of search result dicts with title, url, snippet
    """
    cache = get_tavily_cache()

    # Check cache first
    cached = cache.get_search_results(query)
    if cached and len(cached.get("results", [])) >= max_results:
        return cached["results"][:max_results]

    # Cache miss - execute search
    tavily_client = get_tavily_client()
    if not tavily_client:
        logger.warning("Tavily client not available for search")
        return []

    try:
        # Tavily search returns list of results
        results = tavily_client.search(query, max_results=max_results)

        # Handle different response formats
        if isinstance(results, dict) and "results" in results:
            result_list = results["results"]
        elif isinstance(results, list):
            result_list = results
        else:
            result_list = []

        # Normalize results format
        normalized = []
        for r in result_list:
            normalized.append({
                "title": r.get("title", "No title"),
                "url": r.get("url", ""),
                "snippet": r.get("content", r.get("snippet", "No description")),
            })

        # Cache results
        cache.save_search_results(query, normalized, max_results)
        return normalized

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return []


async def cached_scrape_url(url: str) -> dict[str, Any]:
    """Scrape URL with MinIO caching.

    Args:
        url: URL to scrape

    Returns:
        Dict with success, content, title, or error
    """
    cache = get_tavily_cache()

    # Check cache first
    cached = cache.get_scraped_content(url)
    if cached:
        return {
            "success": True,
            "content": cached.get("content", ""),
            "title": cached.get("title", ""),
            "from_cache": True,
        }

    # Cache miss - scrape URL
    tavily_client = get_tavily_client()
    if not tavily_client:
        logger.warning("Tavily client not available for scraping")
        return {"success": False, "error": "Tavily client not available"}

    try:
        response = tavily_client.extract(urls=[url])

        if response and "results" in response and response["results"]:
            result = response["results"][0]
            content = result.get("raw_content", "")
            title = result.get("title", "")

            # Cache the scraped content
            cache.save_scraped_content(url, content, title)

            return {
                "success": True,
                "content": content,
                "title": title,
                "from_cache": False,
            }

        return {"success": False, "error": "No content extracted"}

    except Exception as e:
        logger.error(f"Scrape URL error: {e}")
        return {"success": False, "error": str(e)}


def get_tool_definitions(include_deep_research: bool = True):
    """Get LangChain tool definitions for search.

    Args:
        include_deep_research: Whether to include Perplexity deep_research tool

    Returns:
        List of LangChain tools (web_search, scrape_url, deep_research if available)
    """
    from langchain_community.tools.tavily_search import TavilySearchResults
    from langchain_core.tools import tool

    tools = []

    # Get Tavily client
    tavily_client = get_tavily_client()

    if tavily_client:
        # Web search tool - use API key directly
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        web_search = TavilySearchResults(
            max_results=5,
            api_key=tavily_api_key,
            name="web_search",
            description="Search the web for current information. Returns snippets and URLs.",
        )
        tools.append(web_search)

        # URL scraping tool
        @tool
        def scrape_url(url: str) -> str:
            """Scrape and extract main content from a URL.

            Args:
                url: The URL to scrape

            Returns:
                The extracted content from the page
            """
            try:
                response = tavily_client.extract(urls=[url])
                if response and "results" in response and response["results"]:
                    return response["results"][0].get("raw_content", "")
                return "No content found"
            except Exception as e:
                return f"Error scraping URL: {str(e)}"

        tools.append(scrape_url)

    # Check for Perplexity deep research
    perplexity_key = os.getenv("PERPLEXITY_API_KEY")
    if perplexity_key and include_deep_research:

        @tool
        async def deep_research(query: str) -> str:
            """Conduct deep research using Perplexity AI with citations.

            Use this for in-depth research on complex topics that require
            comprehensive analysis and authoritative sources.

            Args:
                query: The research question to investigate

            Returns:
                Detailed research findings with citations
            """
            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.perplexity.ai/chat/completions",
                        headers={
                            "Authorization": f"Bearer {perplexity_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "llama-3.1-sonar-large-128k-online",
                            "messages": [{"role": "user", "content": query}],
                        },
                        timeout=60.0,
                    )
                    data = response.json()
                    if "choices" in data and data["choices"]:
                        return data["choices"][0]["message"]["content"]
                    return "No results from deep research"
            except Exception as e:
                return f"Deep research error: {str(e)}"

        tools.append(deep_research)

    return tools
