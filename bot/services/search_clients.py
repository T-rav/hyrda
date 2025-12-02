"""
Direct search and research API clients

Provides direct integrations for:
- Tavily: Web search and URL scraping
- Perplexity: Deep research with citations
"""

import logging
from typing import Any

import aiohttp

from bot_types import DeepResearchResult, WebScrapeResult, WebSearchResult

logger = logging.getLogger(__name__)


class TavilyClient:
    """Direct Tavily API client for web search and scraping"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.tavily.com"
        self.session: aiohttp.ClientSession | None = None

    async def initialize(self):
        """Initialize the HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("Tavily client initialized")

    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def search(self, query: str, max_results: int = 10) -> list[WebSearchResult]:
        """
        Search the web using Tavily API

        Args:
            query: Search query
            max_results: Maximum number of results (default: 10)

        Returns:
            List of search results with title, url, content (snippet)
        """
        if not self.session:
            await self.initialize()

        try:
            url = f"{self.base_url}/search"
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": False,  # We don't need AI-generated answers
                "include_raw_content": False,  # Just snippets for search
            }

            logger.info(f"Tavily search: {query}")

            async with self.session.post(url, json=payload) as response:  # type: ignore
                response.raise_for_status()
                data = await response.json()

                # Extract results
                results = []
                for item in data.get("results", []):
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get(
                                "content", ""
                            ),  # Tavily calls it 'content'
                        }
                    )

                logger.info(f"Tavily search returned {len(results)} results")
                return results

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    async def scrape_url(self, url: str) -> WebScrapeResult:
        """
        Scrape full content from a URL using Tavily Extract API

        Args:
            url: URL to scrape

        Returns:
            Dict with success, url, title, content (markdown)
        """
        if not self.session:
            await self.initialize()

        try:
            api_url = f"{self.base_url}/extract"
            payload = {
                "api_key": self.api_key,
                "urls": [url],
            }

            logger.info(f"Tavily scraping: {url}")

            async with self.session.post(api_url, json=payload) as response:  # type: ignore
                response.raise_for_status()
                data = await response.json()

                # Extract first result
                results = data.get("results", [])
                if not results:
                    return {"success": False, "url": url, "error": "No content found"}

                result = results[0]
                content = result.get("raw_content", "")

                logger.info(f"Tavily scraped {len(content)} chars from: {url}")
                return {
                    "success": True,
                    "url": url,
                    "title": url.split("/")[-1],  # Simple title fallback
                    "content": content,
                }

        except Exception as e:
            logger.error(f"Tavily scrape failed: {e}")
            return {"success": False, "url": url, "error": str(e)}


class PerplexityClient:
    """Direct Perplexity API client for deep research"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai"
        self.session: aiohttp.ClientSession | None = None

    async def initialize(self):
        """Initialize the HTTP session"""
        if not self.session:
            # Perplexity typically responds in 10-60 seconds, set timeout to 120s for safety
            timeout = aiohttp.ClientTimeout(total=120)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("Perplexity client initialized")

    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def deep_research(self, query: str) -> DeepResearchResult:
        """
        Perform deep research using Perplexity API

        Args:
            query: Research query

        Returns:
            Dict with answer, sources, success
        """
        if not self.session:
            await self.initialize()

        try:
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": "sonar-pro",  # Best model for research with citations
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an expert business intelligence researcher conducting company profile research for B2B sales and consulting. "
                            "Provide comprehensive, strategic answers that reveal:\n"
                            "- Business priorities and strategic initiatives\n"
                            "- Product roadmaps and technology investments\n"
                            "- Engineering challenges, technical debt, and scaling issues\n"
                            "- Leadership priorities and pain points\n"
                            "- Growth signals and consulting opportunities\n\n"
                            "Focus on RECENT information (past 12 months) and cite authoritative sources like:\n"
                            "- Company announcements, earnings calls, SEC filings\n"
                            "- Executive interviews and conference talks\n"
                            "- Industry analyst reports and tech journalism\n"
                            "- Engineering blogs, job postings, and Glassdoor reviews\n\n"
                            "Go beyond basic facts - provide strategic context, implications, and actionable insights."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                "return_citations": True,
                "return_images": False,
                "search_recency_filter": "month",  # Focus on recent information (past month)
                "temperature": 0.2,  # Lower temperature for factual research
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            import time

            start_time = time.time()

            logger.info(f"Perplexity deep research: {query}")

            async with self.session.post(
                url, json=payload, headers=headers
            ) as response:  # type: ignore
                response.raise_for_status()
                data = await response.json()

                # Extract answer and citations
                choices = data.get("choices", [])
                if not choices:
                    return {"success": False, "error": "No response from Perplexity"}

                message = choices[0].get("message", {})
                answer = message.get("content", "")
                citations = data.get("citations", [])

                # Format sources with domain as title
                sources = []
                for url in citations:
                    # Extract a readable title from URL (domain + path)
                    try:
                        from urllib.parse import urlparse

                        parsed = urlparse(url)
                        domain = parsed.netloc.replace("www.", "")
                        # Use domain as title, or path if available
                        path_parts = parsed.path.strip("/").split("/")
                        if path_parts and path_parts[0]:
                            title = f"{domain}/{path_parts[0]}"
                        else:
                            title = domain
                    except Exception:
                        title = url[:50]  # Fallback to truncated URL

                    sources.append({"url": url, "title": title})

                duration = time.time() - start_time

                logger.info(
                    f"Perplexity research completed in {duration:.2f}s: {len(answer)} chars, {len(sources)} sources"
                )
                return {"success": True, "answer": answer, "sources": sources}

        except Exception as e:
            logger.error(f"Perplexity deep research failed: {e}")
            return {"success": False, "error": str(e)}


# Singleton instances
_tavily_client: TavilyClient | None = None
_perplexity_client: PerplexityClient | None = None


def get_tavily_client() -> TavilyClient | None:
    """Get the singleton Tavily client"""
    return _tavily_client


def get_perplexity_client() -> PerplexityClient | None:
    """Get the singleton Perplexity client"""
    return _perplexity_client


async def initialize_search_clients(
    tavily_api_key: str | None = None, perplexity_api_key: str | None = None
):
    """Initialize search client singletons"""
    global _tavily_client, _perplexity_client  # noqa: PLW0603

    if tavily_api_key and not _tavily_client:
        _tavily_client = TavilyClient(tavily_api_key)
        await _tavily_client.initialize()
        logger.info("✅ Tavily client initialized")

    if perplexity_api_key and not _perplexity_client:
        _perplexity_client = PerplexityClient(perplexity_api_key)
        await _perplexity_client.initialize()
        logger.info("✅ Perplexity client initialized")


async def close_search_clients():
    """Close all search clients"""
    global _tavily_client, _perplexity_client  # noqa: PLW0603

    if _tavily_client:
        await _tavily_client.close()
        _tavily_client = None

    if _perplexity_client:
        await _perplexity_client.close()
        _perplexity_client = None

    logger.info("✅ Search clients closed")


def get_tool_definitions(include_deep_research: bool = False) -> list[dict[str, Any]]:
    """
    Get OpenAI-compatible tool definitions for search clients

    Args:
        include_deep_research: Whether to include deep_research tool (default: False, only for LangGraph agents)

    Returns:
        List of tool definitions for function calling
        - Regular chat: web_search + scrape_url (Tavily only)
        - LangGraph agents: web_search + scrape_url + deep_research (Tavily + Perplexity)
    """
    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the web for current, real-time information using Tavily. "
                    "Returns search results with titles, URLs, and snippets. "
                    "Use this first to find relevant URLs, then use scrape_url to get full content.\n\n"
                    "Use this tool when the user asks about:\n"
                    "- Recent news, current events, or today's happenings\n"
                    "- Latest information about any topic\n"
                    "- Real-time data, stock prices, weather, sports scores\n"
                    "- Information that changes frequently or is time-sensitive\n"
                    "- Anything requiring up-to-date knowledge beyond your training cutoff"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "The web search query. Be specific and use keywords for relevant, "
                                "current information. Examples: 'latest AI news 2025', 'current bitcoin price', "
                                "'today's weather New York'"
                            ),
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 10, max: 20)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "scrape_url",
                "description": (
                    "Scrape and extract full content from a specific URL using Tavily. "
                    "Converts webpage to clean text format for analysis. "
                    "Use this AFTER web_search to get detailed content from promising URLs.\n\n"
                    "Best practices:\n"
                    "- First use web_search to find relevant URLs\n"
                    "- Then scrape the 2-3 most relevant URLs for full content\n"
                    "- Scraping provides much more detail than search snippets"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The full URL to scrape (must start with http:// or https://)",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
    ]

    # Conditionally add deep_research tool (only for LangGraph agents)
    if include_deep_research and _perplexity_client:
        deep_research_tool = {
            "type": "function",
            "function": {
                "name": "deep_research",
                "description": (
                    "Perform comprehensive deep research on complex topics using Perplexity AI. "
                    "Returns detailed, well-researched answers with citations and sources. "
                    "Use this for in-depth analysis requiring multiple sources and synthesis.\n\n"
                    "**IMPORTANT - Cost Management:**\n"
                    "This tool is EXPENSIVE (costs money per query). Use strategically:\n\n"
                    "**Strategy:** Start with web_search to explore, then use deep_research on 5-10 key topics that need comprehensive analysis.\n\n"
                    "Best for:\n"
                    "- Complex research questions requiring comprehensive analysis\n"
                    "- Topics needing expert-level understanding and synthesis\n"
                    "- Questions requiring multiple perspectives and sources\n"
                    "- When you need authoritative, well-cited answers\n"
                    "- Academic or professional research queries\n\n"
                    "NOT for:\n"
                    "- Simple factual lookups (use web_search instead)\n"
                    "- Real-time data like stock prices or weather (use web_search)\n"
                    "- Single-source information (use scrape_url instead)\n"
                    "- Exploratory searches (use web_search first)"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "The research question or topic. Be specific and clear about what you want to understand. "
                                "Examples: 'What are the latest developments in quantum computing?', "
                                "'How does CRISPR gene editing work and what are its ethical implications?', "
                                "'Compare different approaches to carbon capture technology'"
                            ),
                        },
                    },
                    "required": ["query"],
                },
            },
        }
        tools.append(deep_research_tool)

    return tools
