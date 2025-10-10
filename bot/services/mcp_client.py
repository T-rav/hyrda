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
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)

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

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
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

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Get OpenAI-compatible tool definitions for WebCat

        Returns:
            List of tool definitions for function calling
        """
        if not self.enabled:
            return []

        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": (
                        "Search the web for current, real-time information. "
                        "Use this tool when the user asks about:\n"
                        "- Recent news, current events, or today's happenings\n"
                        "- Latest information about any topic\n"
                        "- Real-time data, stock prices, weather, sports scores\n"
                        "- Information that changes frequently or is time-sensitive\n"
                        "- Anything requiring up-to-date knowledge beyond your training cutoff\n\n"
                        "The tool returns relevant web search results with titles, URLs, and snippets."
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
                                "description": "Maximum number of results (default: 5)",
                                "default": 5,
                            },
                        },
                        "required": ["query"],
                    },
                },
            }
        ]


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
