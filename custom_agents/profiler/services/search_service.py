"""Lightweight search service for custom agents.

Provides Tavily search client without depending on bot/services.
"""

import logging
import os

logger = logging.getLogger(__name__)


def get_tavily_client():
    """Get Tavily client for web search."""
    api_key = os.getenv("TAVILY_API_KEY")
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


def get_tool_definitions(tavily_client):
    """Get LangChain tool definitions for search.

    Returns:
        List of LangChain tools (web_search, scrape_url, deep_research if available)
    """
    from langchain_community.tools.tavily_search import TavilySearchResults
    from langchain_core.tools import tool

    tools = []

    if tavily_client:
        # Web search tool
        web_search = TavilySearchResults(
            max_results=5,
            api_wrapper=tavily_client,
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
    if perplexity_key:

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
