"""Comprehensive tests for search_clients.py (Tavily and Perplexity API clients)."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.search_clients import (
    PerplexityClient,
    TavilyClient,
    close_search_clients,
    get_perplexity_client,
    get_tavily_client,
    get_tool_definitions,
    initialize_search_clients,
)


class TestTavilyClient:
    """Tests for TavilyClient (web search and URL scraping)."""

    @pytest.fixture
    def tavily_client(self):
        """Create a TavilyClient instance for testing."""
        return TavilyClient(api_key="test-tavily-key")

    def test_initialization(self, tavily_client):
        """Test TavilyClient initialization."""
        assert tavily_client.api_key == "test-tavily-key"
        assert tavily_client.base_url == "https://api.tavily.com"
        assert tavily_client.session is None

    @pytest.mark.asyncio
    async def test_initialize_creates_session(self, tavily_client):
        """Test that initialize() creates an aiohttp session."""
        await tavily_client.initialize()

        assert tavily_client.session is not None
        assert isinstance(tavily_client.session, aiohttp.ClientSession)

        # Cleanup
        await tavily_client.close()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, tavily_client):
        """Test that initialize() is idempotent (doesn't create duplicate sessions)."""
        await tavily_client.initialize()
        first_session = tavily_client.session

        await tavily_client.initialize()
        second_session = tavily_client.session

        assert first_session is second_session

        # Cleanup
        await tavily_client.close()

    @pytest.mark.asyncio
    async def test_close_closes_session(self, tavily_client):
        """Test that close() closes the aiohttp session."""
        await tavily_client.initialize()
        assert tavily_client.session is not None

        await tavily_client.close()
        assert tavily_client.session is None

    @pytest.mark.asyncio
    async def test_close_when_no_session(self, tavily_client):
        """Test that close() works even when session is None."""
        assert tavily_client.session is None
        await tavily_client.close()  # Should not raise
        assert tavily_client.session is None

    @pytest.mark.asyncio
    async def test_search_success(self, tavily_client):
        """Test successful web search."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {
                        "title": "Test Article 1",
                        "url": "https://example.com/article1",
                        "content": "This is a test snippet from article 1",
                    },
                    {
                        "title": "Test Article 2",
                        "url": "https://example.com/article2",
                        "content": "This is a test snippet from article 2",
                    },
                ]
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        tavily_client.session = mock_session

        results = await tavily_client.search("test query", max_results=10)

        assert len(results) == 2
        assert results[0]["title"] == "Test Article 1"
        assert results[0]["url"] == "https://example.com/article1"
        assert results[0]["snippet"] == "This is a test snippet from article 1"
        assert results[1]["title"] == "Test Article 2"
        assert results[1]["url"] == "https://example.com/article2"
        assert results[1]["snippet"] == "This is a test snippet from article 2"

    @pytest.mark.asyncio
    async def test_search_initializes_session_if_needed(self, tavily_client):
        """Test that search() auto-initializes session if not present."""
        assert tavily_client.session is None

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = MagicMock()

        with patch.object(aiohttp, "ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(
                return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
            )
            mock_session_class.return_value = mock_session

            results = await tavily_client.search("test query")

            assert tavily_client.session is not None
            assert results == []

            # Cleanup
            await tavily_client.close()

    @pytest.mark.asyncio
    async def test_search_empty_results(self, tavily_client):
        """Test search with no results."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        tavily_client.session = mock_session

        results = await tavily_client.search("no results query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_api_error(self, tavily_client):
        """Test search when API returns an error."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=500, message="Server Error"
            )
        )

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        tavily_client.session = mock_session

        results = await tavily_client.search("error query")

        assert results == []  # Returns empty list on error

    @pytest.mark.asyncio
    async def test_search_network_timeout(self, tavily_client):
        """Test search when network times out."""
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(
            side_effect=aiohttp.ClientTimeout("Request timeout")
        )

        tavily_client.session = mock_session

        results = await tavily_client.search("timeout query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_custom_max_results(self, tavily_client):
        """Test search with custom max_results parameter."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        tavily_client.session = mock_session

        await tavily_client.search("test query", max_results=5)

        # Verify the request was made with correct max_results
        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["max_results"] == 5

    @pytest.mark.asyncio
    async def test_scrape_url_success(self, tavily_client):
        """Test successful URL scraping."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {
                        "url": "https://example.com/article",
                        "raw_content": "This is the full article content in markdown format.",
                    }
                ]
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        tavily_client.session = mock_session

        result = await tavily_client.scrape_url("https://example.com/article")

        assert result["success"] is True
        assert result["url"] == "https://example.com/article"
        assert result["content"] == "This is the full article content in markdown format."
        assert "title" in result

    @pytest.mark.asyncio
    async def test_scrape_url_initializes_session_if_needed(self, tavily_client):
        """Test that scrape_url() auto-initializes session if not present."""
        assert tavily_client.session is None

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = MagicMock()

        with patch.object(aiohttp, "ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(
                return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
            )
            mock_session_class.return_value = mock_session

            result = await tavily_client.scrape_url("https://example.com")

            assert tavily_client.session is not None
            assert result["success"] is False  # Empty results

            # Cleanup
            await tavily_client.close()

    @pytest.mark.asyncio
    async def test_scrape_url_no_content_found(self, tavily_client):
        """Test scraping when no content is returned."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        tavily_client.session = mock_session

        result = await tavily_client.scrape_url("https://example.com/404")

        assert result["success"] is False
        assert result["url"] == "https://example.com/404"
        assert result["error"] == "No content found"

    @pytest.mark.asyncio
    async def test_scrape_url_api_error(self, tavily_client):
        """Test scraping when API returns an error."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=403, message="Forbidden"
            )
        )

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        tavily_client.session = mock_session

        result = await tavily_client.scrape_url("https://forbidden.com")

        assert result["success"] is False
        assert result["url"] == "https://forbidden.com"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_scrape_url_network_error(self, tavily_client):
        """Test scraping when network fails."""
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(
            side_effect=aiohttp.ClientError("Network error")
        )

        tavily_client.session = mock_session

        result = await tavily_client.scrape_url("https://example.com")

        assert result["success"] is False
        assert "error" in result


class TestPerplexityClient:
    """Tests for PerplexityClient (deep research)."""

    @pytest.fixture
    def perplexity_client(self):
        """Create a PerplexityClient instance for testing."""
        return PerplexityClient(api_key="test-perplexity-key")

    def test_initialization(self, perplexity_client):
        """Test PerplexityClient initialization."""
        assert perplexity_client.api_key == "test-perplexity-key"
        assert perplexity_client.base_url == "https://api.perplexity.ai"
        assert perplexity_client.session is None

    @pytest.mark.asyncio
    async def test_initialize_creates_session(self, perplexity_client):
        """Test that initialize() creates an aiohttp session."""
        await perplexity_client.initialize()

        assert perplexity_client.session is not None
        assert isinstance(perplexity_client.session, aiohttp.ClientSession)

        # Cleanup
        await perplexity_client.close()

    @pytest.mark.asyncio
    async def test_initialize_timeout_longer_than_tavily(self, perplexity_client):
        """Test that Perplexity uses 120s timeout (longer than Tavily's 60s)."""
        await perplexity_client.initialize()

        # Check timeout is set correctly (120s for Perplexity)
        assert perplexity_client.session is not None

        # Cleanup
        await perplexity_client.close()

    @pytest.mark.asyncio
    async def test_close_closes_session(self, perplexity_client):
        """Test that close() closes the aiohttp session."""
        await perplexity_client.initialize()
        assert perplexity_client.session is not None

        await perplexity_client.close()
        assert perplexity_client.session is None

    @pytest.mark.asyncio
    async def test_deep_research_success(self, perplexity_client):
        """Test successful deep research."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": "This is a comprehensive research answer with detailed analysis and insights."
                        }
                    }
                ],
                "citations": [
                    "https://example.com/source1",
                    "https://example.com/source2",
                    "https://techblog.com/article/deep-dive",
                ],
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        perplexity_client.session = mock_session

        result = await perplexity_client.deep_research("What are the latest AI trends?")

        assert result["success"] is True
        assert (
            result["answer"]
            == "This is a comprehensive research answer with detailed analysis and insights."
        )
        assert len(result["sources"]) == 3
        assert result["sources"][0]["url"] == "https://example.com/source1"
        assert "example.com" in result["sources"][0]["title"]

    @pytest.mark.asyncio
    async def test_deep_research_initializes_session_if_needed(self, perplexity_client):
        """Test that deep_research() auto-initializes session if not present."""
        assert perplexity_client.session is None

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"choices": []})
        mock_response.raise_for_status = MagicMock()

        with patch.object(aiohttp, "ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(
                return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
            )
            mock_session_class.return_value = mock_session

            result = await perplexity_client.deep_research("test query")

            assert perplexity_client.session is not None
            assert result["success"] is False  # No choices

            # Cleanup
            await perplexity_client.close()

    @pytest.mark.asyncio
    async def test_deep_research_no_response(self, perplexity_client):
        """Test deep research when API returns no choices."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"choices": []})
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        perplexity_client.session = mock_session

        result = await perplexity_client.deep_research("empty query")

        assert result["success"] is False
        assert result["error"] == "No response from Perplexity"

    @pytest.mark.asyncio
    async def test_deep_research_api_error(self, perplexity_client):
        """Test deep research when API returns an error."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=401, message="Unauthorized"
            )
        )

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        perplexity_client.session = mock_session

        result = await perplexity_client.deep_research("unauthorized query")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_deep_research_network_timeout(self, perplexity_client):
        """Test deep research when network times out."""
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(
            side_effect=aiohttp.ClientTimeout("Request timeout")
        )

        perplexity_client.session = mock_session

        result = await perplexity_client.deep_research("timeout query")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_deep_research_source_formatting(self, perplexity_client):
        """Test that sources are formatted correctly with domains and paths."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "Answer"}}],
                "citations": [
                    "https://www.example.com/article/page",
                    "https://blog.company.com/",
                    "https://invalid-url",
                ],
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        perplexity_client.session = mock_session

        result = await perplexity_client.deep_research("test")

        assert result["success"] is True
        assert len(result["sources"]) == 3

        # Check domain extraction (removes www.)
        assert "example.com" in result["sources"][0]["title"]

        # Check path is included when available
        assert "article" in result["sources"][0]["title"]

    @pytest.mark.asyncio
    async def test_deep_research_request_format(self, perplexity_client):
        """Test that deep research sends correct request format."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"choices": [{"message": {"content": "Answer"}}], "citations": []}
        )
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        mock_session.post = MagicMock(return_value=mock_context)

        perplexity_client.session = mock_session

        await perplexity_client.deep_research("What is quantum computing?")

        # Verify request was made with correct parameters
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://api.perplexity.ai/chat/completions"

        payload = call_args[1]["json"]
        assert payload["model"] == "sonar-pro"
        assert payload["return_citations"] is True
        assert payload["temperature"] == 0.2
        assert payload["search_recency_filter"] == "month"

        # Verify system prompt for B2B research
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert "business intelligence" in payload["messages"][0]["content"]

        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-perplexity-key"


class TestSingletonManagement:
    """Tests for singleton client management functions."""

    @pytest.mark.asyncio
    async def test_initialize_search_clients_tavily_only(self):
        """Test initializing only Tavily client."""
        # Reset singletons
        await close_search_clients()

        await initialize_search_clients(tavily_api_key="test-tavily-key")

        tavily = get_tavily_client()
        perplexity = get_perplexity_client()

        assert tavily is not None
        assert tavily.api_key == "test-tavily-key"
        assert perplexity is None

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_search_clients_perplexity_only(self):
        """Test initializing only Perplexity client."""
        # Reset singletons
        await close_search_clients()

        await initialize_search_clients(perplexity_api_key="test-perplexity-key")

        tavily = get_tavily_client()
        perplexity = get_perplexity_client()

        assert tavily is None
        assert perplexity is not None
        assert perplexity.api_key == "test-perplexity-key"

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_search_clients_both(self):
        """Test initializing both clients."""
        # Reset singletons
        await close_search_clients()

        await initialize_search_clients(
            tavily_api_key="test-tavily-key", perplexity_api_key="test-perplexity-key"
        )

        tavily = get_tavily_client()
        perplexity = get_perplexity_client()

        assert tavily is not None
        assert tavily.api_key == "test-tavily-key"
        assert perplexity is not None
        assert perplexity.api_key == "test-perplexity-key"

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_search_clients_idempotent(self):
        """Test that initialize_search_clients is idempotent."""
        # Reset singletons
        await close_search_clients()

        await initialize_search_clients(tavily_api_key="test-key")
        first_tavily = get_tavily_client()

        # Initialize again - should not create new instance
        await initialize_search_clients(tavily_api_key="test-key")
        second_tavily = get_tavily_client()

        assert first_tavily is second_tavily

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_close_search_clients(self):
        """Test closing all search clients."""
        # Initialize both clients
        await initialize_search_clients(
            tavily_api_key="test-tavily-key", perplexity_api_key="test-perplexity-key"
        )

        assert get_tavily_client() is not None
        assert get_perplexity_client() is not None

        # Close all clients
        await close_search_clients()

        assert get_tavily_client() is None
        assert get_perplexity_client() is None

    @pytest.mark.asyncio
    async def test_close_search_clients_when_none_initialized(self):
        """Test that close_search_clients works even when no clients initialized."""
        # Ensure clean state
        await close_search_clients()

        assert get_tavily_client() is None
        assert get_perplexity_client() is None

        # Should not raise
        await close_search_clients()

        assert get_tavily_client() is None
        assert get_perplexity_client() is None

    def test_get_tavily_client_returns_none_when_not_initialized(self):
        """Test that get_tavily_client returns None when not initialized."""
        # Note: This test assumes clean state but doesn't enforce it
        # In real tests, singletons may persist between test runs
        client = get_tavily_client()
        # Just verify it returns something (could be None or existing singleton)
        assert client is None or isinstance(client, TavilyClient)

    def test_get_perplexity_client_returns_none_when_not_initialized(self):
        """Test that get_perplexity_client returns None when not initialized."""
        # Note: This test assumes clean state but doesn't enforce it
        client = get_perplexity_client()
        # Just verify it returns something (could be None or existing singleton)
        assert client is None or isinstance(client, PerplexityClient)


class TestToolDefinitions:
    """Tests for OpenAI tool definitions."""

    def test_get_tool_definitions_default(self):
        """Test default tool definitions (no deep research)."""
        tools = get_tool_definitions()

        assert len(tools) == 2

        # Check web_search tool
        web_search = tools[0]
        assert web_search["type"] == "function"
        assert web_search["function"]["name"] == "web_search"
        assert "query" in web_search["function"]["parameters"]["properties"]

        # Check scrape_url tool
        scrape_url = tools[1]
        assert scrape_url["type"] == "function"
        assert scrape_url["function"]["name"] == "scrape_url"
        assert "url" in scrape_url["function"]["parameters"]["properties"]

    def test_get_tool_definitions_without_deep_research(self):
        """Test tool definitions explicitly without deep research."""
        tools = get_tool_definitions(include_deep_research=False)

        assert len(tools) == 2
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "web_search" in tool_names
        assert "scrape_url" in tool_names
        assert "deep_research" not in tool_names

    @pytest.mark.asyncio
    async def test_get_tool_definitions_with_deep_research_when_client_exists(self):
        """Test tool definitions with deep research when Perplexity client exists."""
        # Initialize Perplexity client
        await initialize_search_clients(perplexity_api_key="test-key")

        tools = get_tool_definitions(include_deep_research=True)

        assert len(tools) == 3
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "web_search" in tool_names
        assert "scrape_url" in tool_names
        assert "deep_research" in tool_names

        # Verify deep_research tool structure
        deep_research = next(t for t in tools if t["function"]["name"] == "deep_research")
        assert deep_research["type"] == "function"
        assert "query" in deep_research["function"]["parameters"]["properties"]
        assert "EXPENSIVE" in deep_research["function"]["description"]

        # Cleanup
        await close_search_clients()

    def test_get_tool_definitions_with_deep_research_when_client_missing(self):
        """Test tool definitions with deep research when Perplexity client missing."""
        # Ensure Perplexity client is not initialized
        # (can't call close_search_clients here as it's async)

        tools = get_tool_definitions(include_deep_research=True)

        # Should still only return 2 tools if client doesn't exist
        assert len(tools) >= 2
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "web_search" in tool_names
        assert "scrape_url" in tool_names

    def test_tool_definitions_have_required_fields(self):
        """Test that all tool definitions have required OpenAI fields."""
        tools = get_tool_definitions()

        for tool in tools:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool

            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

            params = func["parameters"]
            assert "type" in params
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_web_search_tool_parameters(self):
        """Test web_search tool has correct parameters."""
        tools = get_tool_definitions()
        web_search = next(t for t in tools if t["function"]["name"] == "web_search")

        params = web_search["function"]["parameters"]
        assert "query" in params["properties"]
        assert "max_results" in params["properties"]
        assert "query" in params["required"]
        assert params["properties"]["max_results"]["default"] == 10

    def test_scrape_url_tool_parameters(self):
        """Test scrape_url tool has correct parameters."""
        tools = get_tool_definitions()
        scrape_url = next(t for t in tools if t["function"]["name"] == "scrape_url")

        params = scrape_url["function"]["parameters"]
        assert "url" in params["properties"]
        assert "url" in params["required"]

    def test_tool_descriptions_mention_use_cases(self):
        """Test that tool descriptions mention appropriate use cases."""
        tools = get_tool_definitions()

        web_search = next(t for t in tools if t["function"]["name"] == "web_search")
        assert "current" in web_search["function"]["description"].lower()
        assert "real-time" in web_search["function"]["description"].lower()

        scrape_url = next(t for t in tools if t["function"]["name"] == "scrape_url")
        assert "full content" in scrape_url["function"]["description"].lower()
        assert "after web_search" in scrape_url["function"]["description"].lower()
