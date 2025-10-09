"""
MCP (Model Context Protocol) client for tool integration

Connects to MCP servers like WebCat for web search capabilities.
"""

import logging
from typing import Any

import aiohttp

from config.settings import MCPSettings

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for communicating with MCP servers"""

    def __init__(self, settings: MCPSettings):
        self.settings = settings
        self.session: aiohttp.ClientSession | None = None

    async def initialize(self):
        """Initialize the MCP client session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("MCP client initialized")

    async def close(self):
        """Close the MCP client session"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("MCP client closed")

    async def call_tool(
        self, server_url: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Call a tool on an MCP server

        Args:
            server_url: Base URL of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool response data
        """
        if not self.session:
            await self.initialize()

        url = f"{server_url}/tools/{tool_name}"

        try:
            logger.info(f"Calling MCP tool: {tool_name} at {url}")
            logger.debug(f"Arguments: {arguments}")

            async with self.session.post(  # type: ignore
                url, json=arguments, headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"MCP tool {tool_name} succeeded")
                return result

        except aiohttp.ClientError as e:
            logger.error(f"MCP tool call failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling MCP tool: {e}")
            raise

    async def list_tools(self, server_url: str) -> list[dict[str, Any]]:
        """
        List available tools from an MCP server

        Args:
            server_url: Base URL of the MCP server

        Returns:
            List of tool definitions
        """
        if not self.session:
            await self.initialize()

        url = f"{server_url}/tools"

        try:
            async with self.session.get(url) as response:  # type: ignore
                response.raise_for_status()
                result = await response.json()
                return result.get("tools", [])
        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []


class WebCatClient:
    """WebCat-specific MCP client for web search"""

    def __init__(self, settings: MCPSettings):
        self.settings = settings
        self.mcp_client = MCPClient(settings)
        self.enabled = settings.webcat_enabled
        self.base_url = f"http://{settings.webcat_host}:{settings.webcat_port}"

    async def initialize(self):
        """Initialize the WebCat client"""
        if self.enabled:
            await self.mcp_client.initialize()
            logger.info(f"WebCat MCP client initialized at {self.base_url}")

    async def close(self):
        """Close the WebCat client"""
        await self.mcp_client.close()

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

        try:
            result = await self.mcp_client.call_tool(
                server_url=self.base_url,
                tool_name="search",
                arguments={"query": query, "maxResults": max_results},
            )

            # Parse search results from MCP response
            results = result.get("results", [])
            logger.info(f"WebCat search returned {len(results)} results for: {query}")
            return results

        except Exception as e:
            logger.error(f"WebCat search failed: {e}")
            return []

    async def fetch_url(self, url: str) -> str | None:
        """
        Fetch content from a URL using WebCat

        Args:
            url: URL to fetch

        Returns:
            Page content or None if failed
        """
        if not self.enabled:
            logger.warning("WebCat is disabled")
            return None

        try:
            result = await self.mcp_client.call_tool(
                server_url=self.base_url, tool_name="fetch", arguments={"url": url}
            )

            content = result.get("content", "")
            logger.info(f"WebCat fetched {len(content)} characters from {url}")
            return content

        except Exception as e:
            logger.error(f"WebCat fetch failed: {e}")
            return None

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
                    "description": "Search the web for current information. Use this when the user asks about recent events, current data, or information not in your knowledge base.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default: 5)",
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
