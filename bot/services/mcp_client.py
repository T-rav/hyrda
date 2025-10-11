"""
MCP (Model Context Protocol) client for tool integration

Connects to MCP servers like WebCat for web search capabilities.
"""

import logging
from typing import Any

import aiohttp

from config.settings import MCPSettings

logger = logging.getLogger(__name__)


class WebCatClient:
    """WebCat-specific MCP client for web search using FastMCP protocol"""

    def __init__(self, settings: MCPSettings):
        self.settings = settings
        self.enabled = settings.webcat_enabled
        self.base_url = f"http://{settings.webcat_host}:{settings.webcat_port}"
        self.session: aiohttp.ClientSession | None = None
        self.mcp_session_id: str | None = None

    async def initialize(self):
        """Initialize the WebCat client and MCP session"""
        if not self.enabled:
            return

        if not self.session:
            # Increase timeout for deep_research operations (10 minutes)
            # deep_research 'high' effort can take 3-5 minutes, allow generous buffer
            # Set all timeout components to 600s to prevent premature disconnections
            timeout = aiohttp.ClientTimeout(
                total=600,  # Total request timeout (10 minutes)
                connect=60,  # Connection timeout (1 minute)
                sock_read=600,  # Socket read timeout (10 minutes) - CRITICAL for SSE streams
                sock_connect=60,  # Socket connect timeout (1 minute)
            )
            # Increase max_line_size to handle large SSE chunks from WebCat (default is 8KB)
            # WebCat can send large search results that exceed aiohttp's readline limit
            connector = aiohttp.TCPConnector(limit_per_host=10)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                read_bufsize=1024 * 1024,  # 1MB read buffer (default is 64KB)
            )

        # Initialize MCP session
        await self._init_mcp_session()
        logger.info(f"WebCat MCP client initialized at {self.base_url}")

    async def close(self):
        """Close the WebCat client"""
        self.mcp_session_id = None
        if self.session:
            await self.session.close()
            self.session = None

    async def _init_mcp_session(self):
        """Initialize MCP session with WebCat"""
        try:
            url = f"{self.base_url}/mcp"
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "InsightMesh", "version": "1.0.0"},
                },
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }

            if self.settings.webcat_api_key:
                headers["Authorization"] = f"Bearer {self.settings.webcat_api_key}"

            async with self.session.post(
                url, json=payload, headers=headers
            ) as response:  # type: ignore
                response.raise_for_status()
                self.mcp_session_id = response.headers.get("mcp-session-id")

                if not self.mcp_session_id:
                    logger.warning("No MCP session ID received from WebCat")
                else:
                    logger.debug(f"MCP session initialized: {self.mcp_session_id}")

            # Send initialized notification
            if self.mcp_session_id:
                initialized_payload = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                }

                initialized_headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": self.mcp_session_id,
                }

                if self.settings.webcat_api_key:
                    initialized_headers["Authorization"] = (
                        f"Bearer {self.settings.webcat_api_key}"
                    )

                async with self.session.post(
                    url, json=initialized_payload, headers=initialized_headers
                ) as response:  # type: ignore
                    response.raise_for_status()

        except Exception as e:
            logger.error(f"Failed to initialize MCP session: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

    async def search(self, query: str, max_results: int = 15) -> list[dict[str, Any]]:
        """
        Search the web using WebCat

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of search results with title, url, and snippet
        """
        if not self.enabled:
            logger.warning("WebCat is disabled")
            return []

        if not self.session:
            await self.initialize()

        if not self.mcp_session_id:
            await self._init_mcp_session()
            if not self.mcp_session_id:
                logger.error("Cannot search without MCP session")
                return []

        try:
            import json

            url = f"{self.base_url}/mcp"
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": query}},
                "id": 1,
            }

            logger.info(f"WebCat search: {query}")

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": self.mcp_session_id,
            }

            if self.settings.webcat_api_key:
                headers["Authorization"] = f"Bearer {self.settings.webcat_api_key}"

            results = []
            async with self.session.post(
                url, json=payload, headers=headers
            ) as response:  # type: ignore
                response.raise_for_status()

                # Parse SSE stream
                async for line in response.content:
                    line_str = line.decode("utf-8").strip()

                    if line_str.startswith("data: "):
                        data_str = line_str[6:]

                        if data_str and data_str != "[DONE]":
                            try:
                                data = json.loads(data_str)

                                # Check for result
                                if "result" in data:
                                    result_data = data["result"]

                                    # Handle different response structures
                                    if isinstance(result_data, dict):
                                        # Check for content array
                                        if "content" in result_data:
                                            for item in result_data["content"]:
                                                if item.get("type") == "text":
                                                    text = item.get("text", "")
                                                    try:
                                                        parsed = json.loads(text)
                                                        if "results" in parsed:
                                                            results = parsed["results"]
                                                    except json.JSONDecodeError:
                                                        pass
                                        # Or structured content
                                        elif "structuredContent" in result_data:
                                            structured = result_data[
                                                "structuredContent"
                                            ]
                                            if "results" in structured:
                                                results = structured["results"]
                                        # Or direct results
                                        elif "results" in result_data:
                                            results = result_data["results"]
                                    elif isinstance(result_data, list):
                                        results = result_data
                                    break

                            except json.JSONDecodeError:
                                continue

            logger.info(f"WebCat search returned {len(results)} results for: {query}")
            return results

        except Exception as e:
            logger.error(f"WebCat search failed: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def scrape_url(self, url: str) -> dict[str, Any]:
        """
        Scrape full content from a specific URL

        Args:
            url: URL to scrape

        Returns:
            Dict with success, url, title, content (markdown)
        """
        if not self.enabled:
            logger.warning("WebCat is disabled")
            return {"success": False, "url": url, "error": "WebCat disabled"}

        if not self.session:
            await self.initialize()

        if not self.mcp_session_id:
            await self._init_mcp_session()
            if not self.mcp_session_id:
                logger.error("Cannot scrape without MCP session")
                return {"success": False, "url": url, "error": "No MCP session"}

        try:
            import json

            mcp_url = f"{self.base_url}/mcp"
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "scrape_url", "arguments": {"url": url}},
                "id": 1,
            }

            logger.info(f"WebCat scraping: {url}")

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": self.mcp_session_id,
            }

            if self.settings.webcat_api_key:
                headers["Authorization"] = f"Bearer {self.settings.webcat_api_key}"

            result = {}
            async with self.session.post(
                mcp_url, json=payload, headers=headers
            ) as response:  # type: ignore
                response.raise_for_status()

                # Parse SSE stream
                async for line in response.content:
                    line_str = line.decode("utf-8").strip()

                    if line_str.startswith("data: "):
                        data_str = line_str[6:]

                        if data_str and data_str != "[DONE]":
                            try:
                                data = json.loads(data_str)

                                if "result" in data:
                                    result_data = data["result"]

                                    # Extract scraped content
                                    if isinstance(result_data, dict):
                                        if "content" in result_data:
                                            for item in result_data["content"]:
                                                if item.get("type") == "text":
                                                    text = item.get("text", "")
                                                    try:
                                                        result = json.loads(text)
                                                    except json.JSONDecodeError:
                                                        result = {"content": text}
                                        else:
                                            result = result_data
                                    break

                            except json.JSONDecodeError:
                                continue

            logger.info(
                f"WebCat scraped {len(result.get('content', ''))} chars from: {url}"
            )
            return result

        except Exception as e:
            logger.error(f"WebCat scrape failed: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "url": url, "error": str(e)}

    async def deep_research(self, query: str, effort: str = "medium") -> dict[str, Any]:
        """
        Perform deep research using Perplexity AI for comprehensive answers

        Args:
            query: Research query requiring in-depth analysis
            effort: Research effort level - "low" (5 queries), "medium" (15 queries), "high" (25 queries)

        Returns:
            Dict with success, answer, sources, and metadata
        """
        if not self.enabled:
            logger.warning("WebCat is disabled")
            return {"success": False, "error": "WebCat disabled"}

        if not self.session:
            await self.initialize()

        if not self.mcp_session_id:
            await self._init_mcp_session()
            if not self.mcp_session_id:
                logger.error("Cannot perform deep research without MCP session")
                return {"success": False, "error": "No MCP session"}

        try:
            import json

            mcp_url = f"{self.base_url}/mcp"
            # WebCat 2.5.0 deep_research doesn't accept 'effort' parameter
            # Remove it from arguments to avoid validation error
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "deep_research",
                    "arguments": {"query": query},
                },
                "id": 1,
            }

            logger.info(f"WebCat deep research ({effort} effort): {query}")

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": self.mcp_session_id,
            }

            if self.settings.webcat_api_key:
                headers["Authorization"] = f"Bearer {self.settings.webcat_api_key}"

            result = {}
            async with self.session.post(
                mcp_url, json=payload, headers=headers
            ) as response:  # type: ignore
                response.raise_for_status()

                # Parse SSE stream
                async for line in response.content:
                    line_str = line.decode("utf-8").strip()

                    if line_str.startswith("data: "):
                        data_str = line_str[6:]

                        if data_str and data_str != "[DONE]":
                            try:
                                data = json.loads(data_str)

                                if "result" in data:
                                    result_data = data["result"]

                                    # Extract deep research results
                                    if isinstance(result_data, dict):
                                        if "content" in result_data:
                                            for item in result_data["content"]:
                                                if item.get("type") == "text":
                                                    text = item.get("text", "")
                                                    logger.debug(
                                                        f"Received text response: {len(text)} chars"
                                                    )
                                                    try:
                                                        parsed = json.loads(text)
                                                        logger.debug(
                                                            f"Parsed JSON successfully: {list(parsed.keys())}"
                                                        )

                                                        # WebCat returns SearchResponse format:
                                                        # {"query": "...", "results": [{"content": "..."}], "error": null}
                                                        # Extract the actual research content from results[0].content
                                                        # The content is markdown with embedded sources at the bottom
                                                        if (
                                                            "results" in parsed
                                                            and parsed["results"]
                                                        ):
                                                            result_item = parsed[
                                                                "results"
                                                            ][0]
                                                            content = result_item.get(
                                                                "content", ""
                                                            )

                                                            # Extract sources from markdown (they're at the bottom after "## Sources")
                                                            sources = []
                                                            if "## Sources" in content:
                                                                sources_section = (
                                                                    content.split(
                                                                        "## Sources"
                                                                    )[1]
                                                                )
                                                                # Parse numbered sources like "1. https://..."
                                                                for raw_line in sources_section.split(
                                                                    "\n"
                                                                ):
                                                                    stripped_line = (
                                                                        raw_line.strip()
                                                                    )
                                                                    if (
                                                                        stripped_line
                                                                        and (
                                                                            stripped_line[
                                                                                0
                                                                            ].isdigit()
                                                                            or stripped_line.startswith(
                                                                                "- "
                                                                            )
                                                                        )
                                                                    ):
                                                                        # Remove leading number/dash and whitespace
                                                                        url = stripped_line.lstrip(
                                                                            "0123456789.-() \t"
                                                                        )
                                                                        if url.startswith(
                                                                            "http"
                                                                        ):
                                                                            sources.append(
                                                                                url
                                                                            )

                                                            result = {
                                                                "answer": content,
                                                                "query": parsed.get(
                                                                    "query", query
                                                                ),
                                                                "source": parsed.get(
                                                                    "search_source",
                                                                    "Perplexity Deep Research",
                                                                ),
                                                                "sources": sources,  # Extracted from markdown
                                                                "success": True,
                                                            }
                                                        elif (
                                                            "error" in parsed
                                                            and parsed["error"]
                                                        ):
                                                            result = {
                                                                "success": False,
                                                                "error": parsed[
                                                                    "error"
                                                                ],
                                                                "query": query,
                                                            }
                                                        else:
                                                            # Fallback: use parsed directly
                                                            result = parsed
                                                    except json.JSONDecodeError:
                                                        logger.debug(
                                                            "Failed to parse as JSON, using raw text"
                                                        )
                                                        result = {
                                                            "answer": text,
                                                            "success": True,
                                                        }
                                        else:
                                            logger.debug(
                                                f"Using result_data directly: {list(result_data.keys())}"
                                            )
                                            result = result_data
                                    break

                            except json.JSONDecodeError:
                                continue

            answer_len = len(result.get("answer", ""))
            success = result.get("success", answer_len > 0)
            logger.info(
                f"WebCat deep research completed for: {query} (answer length: {answer_len}, success: {success}, keys: {list(result.keys())})"
            )
            return result

        except Exception as e:
            logger.error(f"WebCat deep research failed: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Get OpenAI-compatible tool definitions for WebCat

        Returns:
            List of tool definitions for function calling (search + scrape + optional deep_research)
        """
        if not self.enabled:
            return []

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": (
                        "Search the web for current, real-time information. "
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
                                "description": "Maximum number of results (default: 15, max: 20)",
                                "default": 15,
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
                        "Scrape and extract full content from a specific URL. "
                        "Converts webpage to clean markdown format for analysis. "
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

        # Conditionally add deep_research tool if enabled
        if self.settings.webcat_deep_research_enabled:
            deep_research_tool = {
                "type": "function",
                "function": {
                    "name": "deep_research",
                    "description": (
                        "Perform comprehensive deep research on complex topics using Perplexity AI. "
                        "Returns detailed, well-researched answers with citations and sources. "
                        "Use this for in-depth analysis requiring multiple sources and synthesis.\n\n"
                        "**IMPORTANT - Cost Management:**\n"
                        "This tool is EXPENSIVE - takes 2-3 minutes per query. Use strategically:\n\n"
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
        else:
            logger.info(
                "deep_research tool disabled via MCP_WEBCAT_DEEP_RESEARCH_ENABLED=false"
            )

        return tools


# Singleton instance
_webcat_client: WebCatClient | None = None


def get_webcat_client() -> WebCatClient | None:
    """Get the singleton WebCat client instance"""
    return _webcat_client


async def initialize_webcat_client(settings: MCPSettings) -> WebCatClient:
    """Initialize the WebCat client singleton"""
    global _webcat_client  # noqa: PLW0603
    if _webcat_client is None:
        _webcat_client = WebCatClient(settings)
        await _webcat_client.initialize()
    return _webcat_client
