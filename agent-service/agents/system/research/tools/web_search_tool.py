"""Enhanced web search tool for deep research.

Better than OpenAI/Gemini research with multi-source search and dual caching.
Automatically caches all search results to Redis (fast) + MinIO (persistent).
"""

import contextlib
import hashlib
import logging
import os
from typing import Any

import redis.asyncio as redis
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from ..services.file_cache import ResearchFileCache

logger = logging.getLogger(__name__)


class WebSearchInput(BaseModel):
    """Input for web search."""

    query: str = Field(
        min_length=3,
        description="Search query - be specific about what you're looking for",
    )
    depth: str = Field(
        default="standard",
        description='Search depth: "quick" (3 results), "standard" (5 results), "deep" (10 results)',
    )


class EnhancedWebSearchTool(BaseTool):
    """Enhanced web search with multiple sources and dual caching.

    Searches across multiple sources (Tavily, Perplexity) and aggregates results
    for comprehensive coverage. Caches in Redis (fast) + MinIO (persistent).
    """

    name: str = "web_search"
    description: str = (
        "Search the web for current information across multiple sources. "
        "Use for recent events, news, company updates, technology trends, "
        "market data, or any information not in your training data. "
        "Returns comprehensive results with URLs and snippets."
    )
    args_schema: type[BaseModel] = WebSearchInput

    tavily_api_key: str | None = None
    perplexity_api_key: str | None = None
    file_cache: ResearchFileCache | None = None  # MinIO caching
    redis_client: redis.Redis | None = None  # Redis caching
    redis_url: str = "redis://redis:6379"
    redis_ttl: int = 3600  # 1 hour

    class Config:
        """Config."""

        arbitrary_types_allowed = True

    def __init__(
        self,
        tavily_api_key: str | None = None,
        perplexity_api_key: str | None = None,
        file_cache: ResearchFileCache | None = None,
        redis_url: str | None = None,
        **kwargs: Any,
    ):
        """Initialize with API keys and dual cache.

        Args:
            tavily_api_key: Tavily API key
            perplexity_api_key: Perplexity API key
            file_cache: Optional file cache for MinIO caching
            redis_url: Redis connection URL
            **kwargs: Additional BaseTool arguments
        """
        kwargs["tavily_api_key"] = tavily_api_key or os.getenv("TAVILY_API_KEY")
        kwargs["perplexity_api_key"] = perplexity_api_key or os.getenv(
            "PERPLEXITY_API_KEY"
        )
        kwargs["file_cache"] = file_cache
        kwargs["redis_url"] = redis_url or os.getenv(
            "CACHE_REDIS_URL", "redis://redis:6379"
        )
        super().__init__(**kwargs)

        # Initialize MinIO file cache if not provided
        if not self.file_cache:
            try:
                self.file_cache = ResearchFileCache()
                logger.info("Initialized MinIO caching for web search results")
            except Exception as e:
                logger.warning(
                    f"MinIO cache unavailable: {e}, continuing without MinIO caching"
                )

        # Initialize Redis cache
        self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis client for fast caching."""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            logger.info(f"Initialized Redis caching at {self.redis_url}")
        except Exception as e:
            logger.warning(f"Redis init failed: {e}, continuing without Redis caching")
            self.redis_client = None

    def _get_cache_key(self, query: str, depth: str = "standard") -> str:
        """Generate cache key for query."""
        # Use hash to avoid key length issues
        query_hash = hashlib.md5(f"{query}:{depth}".encode()).hexdigest()
        return f"web_search:{query_hash}"

    def _run(self, query: str, depth: str = "standard") -> str:
        """Execute web search with automatic caching.

        Args:
            query: Search query
            depth: Search depth (quick, standard, deep)

        Returns:
            Formatted search results with URLs
        """
        try:
            # Check cache first (only if not deep search - deep always fetches fresh)
            if depth != "deep":
                cached_results = self._check_dual_cache(query, depth)
                if cached_results:
                    logger.info(f"✅ Cache hit for query: {query[:50]}...")
                    return f"📦 (From cache)\n\n{cached_results}"

            # Determine result count based on depth
            max_results = {"quick": 3, "standard": 5, "deep": 10}.get(depth, 5)

            results = []

            # Try Tavily search first (faster, more structured)
            if self.tavily_api_key:
                tavily_results = self._search_tavily(query, max_results)
                if tavily_results:
                    results.extend(tavily_results)

            # Fallback to Perplexity if Tavily unavailable or for deep searches
            if (not results or depth == "deep") and self.perplexity_api_key:
                perplexity_results = self._search_perplexity(query)
                if perplexity_results:
                    results.append(perplexity_results)

            if not results:
                return "⚠️ Web search unavailable - no API keys configured"

            # Format results
            output = [f"🔍 Web search results for: {query}\n"]
            for i, result in enumerate(results[:max_results], 1):
                output.append(f"\n{i}. {result}")

            final_output = "".join(output)

            # Auto-cache results in both Redis and MinIO
            self._cache_dual(query, final_output, depth)

            return final_output

        except Exception as e:
            logger.error(f"Error in web search: {e}")
            return f"❌ Web search error: {str(e)}"

    def _check_dual_cache(self, query: str, depth: str = "standard") -> str | None:
        """Check if search results are cached (Redis first, MinIO fallback).

        Args:
            query: Search query
            depth: Search depth

        Returns:
            Cached results or None
        """
        cache_key = self._get_cache_key(query, depth)

        # Try Redis first (fastest)
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    logger.info(f"✅ Redis cache hit for: {query[:50]}...")
                    return cached
            except Exception as e:
                logger.warning(f"Redis cache check failed: {e}")

        # Try MinIO fallback
        if self.file_cache:
            try:
                # Search cache for this query
                cached_files = self.file_cache.search_cache(query, file_type="web_page")

                if cached_files:
                    # Return most recent cached result
                    latest = sorted(
                        cached_files, key=lambda f: f.cached_at, reverse=True
                    )[0]
                    content = self.file_cache.retrieve_file(latest.file_path)
                    if content:
                        logger.info(f"✅ MinIO cache hit for: {query[:50]}...")
                        # Re-cache in Redis for fast access
                        if self.redis_client:
                            with contextlib.suppress(Exception):
                                self.redis_client.setex(
                                    cache_key, self.redis_ttl, str(content)
                                )
                        return str(content)
            except Exception as e:
                logger.warning(f"MinIO cache check failed: {e}")

        return None

    def _cache_dual(self, query: str, results: str, depth: str) -> None:
        """Cache search results in both Redis and MinIO (fire and forget).

        Args:
            query: Search query
            results: Search results to cache
            depth: Search depth
        """
        cache_key = self._get_cache_key(query, depth)

        # Cache in Redis (fast access)
        if self.redis_client:
            try:
                self.redis_client.setex(cache_key, self.redis_ttl, results)
                logger.info(f"✅ Cached to Redis: {query[:50]}...")
            except Exception as e:
                logger.warning(f"Failed to cache to Redis: {e}")

        # Cache in MinIO (long-term storage)
        if self.file_cache:
            try:
                metadata = {
                    "query": query,
                    "depth": depth,
                    "source": "web_search",
                    "title": f"web_search_{query[:50]}",
                }
                self.file_cache.cache_file("web_page", results, metadata)
                logger.info(f"✅ Cached to MinIO: {query[:50]}...")
            except Exception as e:
                logger.warning(f"Failed to cache to MinIO: {e}")

    def _search_tavily(self, query: str, max_results: int) -> list[str]:
        """Search using Tavily API.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of formatted results
        """
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.tavily_api_key)
            response = client.search(query, max_results=max_results)

            results = []
            for item in response.get("results", []):
                title = item.get("title", "No title")
                url = item.get("url", "")
                content = item.get("content", "")[:200]  # First 200 chars
                results.append(f"**{title}**\n   {content}...\n   🔗 {url}")

            logger.info(f"Tavily search returned {len(results)} results")
            return results
        except ImportError:
            logger.warning("Tavily package not installed")
            return []
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []

    def _search_perplexity(self, query: str) -> str | None:
        """Search using Perplexity API for deep research.

        Args:
            query: Search query

        Returns:
            Formatted research summary
        """
        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self.perplexity_api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": "llama-3.1-sonar-large-128k-online",
                "messages": [
                    {
                        "role": "user",
                        "content": f"Research and summarize: {query}",
                    }
                ],
            }

            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.info("Perplexity search completed")
                return f"**Deep Research Summary**\n{content}"
            else:
                logger.error(f"Perplexity API error: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Perplexity search error: {e}")
            return None
