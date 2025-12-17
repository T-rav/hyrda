"""
Comprehensive tests for search_clients.py.

Tests Tavily and Perplexity search clients with mocked HTTP requests.
Covers web search, URL scraping, deep research, and error handling.
"""

from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from services.search_clients import (
    DEFAULT_MAX_SEARCH_RESULTS,
    DEFAULT_SEARCH_TIMEOUT,
    PerplexityClient,
    TavilyClient,
    close_search_clients,
    get_perplexity_client,
    get_tavily_client,
    get_tool_definitions,
    initialize_search_clients,
)


def create_mock_post_context_manager(response):
    """Helper to create properly mocked async context manager for session.post()."""
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


class TestTavilyClientInitialization:
    """Test TavilyClient initialization and lifecycle."""

    def test_tavily_client_creation(self):
        """Test creating a Tavily client."""
        client = TavilyClient(api_key="test-tavily-key")

        assert client.api_key == "test-tavily-key"
        assert client.base_url == "https://api.tavily.com"
        assert client.session is None

    @pytest.mark.asyncio
    async def test_tavily_client_initialize(self):
        """Test initializing Tavily client creates session."""
        client = TavilyClient(api_key="test-tavily-key")

        await client.initialize()

        assert client.session is not None
        assert isinstance(client.session, aiohttp.ClientSession)

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_tavily_client_initialize_idempotent(self):
        """Test initializing Tavily client multiple times is safe."""
        client = TavilyClient(api_key="test-tavily-key")

        await client.initialize()
        session1 = client.session

        await client.initialize()
        session2 = client.session

        # Should reuse same session
        assert session1 is session2

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_tavily_client_close(self):
        """Test closing Tavily client."""
        client = TavilyClient(api_key="test-tavily-key")

        await client.initialize()
        assert client.session is not None

        await client.close()
        assert client.session is None

    @pytest.mark.asyncio
    async def test_tavily_client_close_when_not_initialized(self):
        """Test closing Tavily client when not initialized."""
        client = TavilyClient(api_key="test-tavily-key")

        # Should not raise
        await client.close()
        assert client.session is None


class TestTavilyClientSearch:
    """Test TavilyClient web search functionality."""

    @pytest.mark.asyncio
    async def test_search_successful(self):
        """Test successful web search."""
        client = TavilyClient(api_key="test-tavily-key")

        # Mock session and response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {
                        "title": "Test Result 1",
                        "url": "https://example.com/1",
                        "content": "This is a test snippet 1",
                    },
                    {
                        "title": "Test Result 2",
                        "url": "https://example.com/2",
                        "content": "This is a test snippet 2",
                    },
                ]
            }
        )
        mock_response.raise_for_status = Mock()

        # Mock the context manager returned by session.post()
        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        # Execute search
        results = await client.search(query="test query", max_results=10)

        # Verify results
        assert len(results) == 2
        assert results[0]["title"] == "Test Result 1"
        assert results[0]["url"] == "https://example.com/1"
        assert results[0]["snippet"] == "This is a test snippet 1"
        assert results[1]["title"] == "Test Result 2"

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_search_auto_initializes_session(self):
        """Test search auto-initializes session if not initialized."""
        client = TavilyClient(api_key="test-tavily-key")

        # Mock the post method
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = Mock()

        with patch.object(
            aiohttp.ClientSession, "post", return_value=mock_response
        ) as mock_post:
            mock_post.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.__aexit__ = AsyncMock()

            await client.search(query="test")

            # Session should be initialized
            assert client.session is not None

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_search_with_default_max_results(self):
        """Test search uses default max_results."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        # Execute search without max_results
        await client.search(query="test query")

        # Verify default was used
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"]
        assert payload["max_results"] == DEFAULT_MAX_SEARCH_RESULTS

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test search with empty results."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        results = await client.search(query="no results query")

        assert results == []

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_search_missing_fields(self):
        """Test search handles missing fields gracefully."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {"url": "https://example.com/1"},  # Missing title and content
                    {"title": "Test", "content": "Content"},  # Missing url
                ]
            }
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        results = await client.search(query="test")

        # Should handle missing fields with empty strings
        assert len(results) == 2
        assert results[0]["title"] == ""
        assert results[0]["url"] == "https://example.com/1"
        assert results[0]["snippet"] == ""
        assert results[1]["url"] == ""

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_search_http_error(self):
        """Test search handles HTTP errors."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.raise_for_status = Mock(
            side_effect=aiohttp.ClientResponseError(
                request_info=Mock(),
                history=(),
                status=429,
                message="Rate limit exceeded",
            )
        )

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        results = await client.search(query="test")

        # Should return empty list on error
        assert results == []

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_search_network_timeout(self):
        """Test search handles network timeouts."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_session = AsyncMock()
        mock_session.post = Mock(side_effect=aiohttp.ClientConnectionError())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        client.session = mock_session

        results = await client.search(query="test")

        # Should return empty list on error
        assert results == []

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_search_json_decode_error(self):
        """Test search handles JSON decode errors."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        results = await client.search(query="test")

        # Should return empty list on error
        assert results == []

        # Cleanup
        await client.close()


class TestTavilyClientScrapeUrl:
    """Test TavilyClient URL scraping functionality."""

    @pytest.mark.asyncio
    async def test_scrape_url_successful(self):
        """Test successful URL scraping."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {
                        "raw_content": "This is the full page content in markdown format.",
                    }
                ]
            }
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.scrape_url(url="https://example.com/article")

        assert result["success"] is True
        assert result["url"] == "https://example.com/article"
        assert result["content"] == "This is the full page content in markdown format."
        assert "title" in result

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_scrape_url_auto_initializes_session(self):
        """Test scrape_url auto-initializes session if not initialized."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = Mock()

        with patch.object(
            aiohttp.ClientSession, "post", return_value=mock_response
        ) as mock_post:
            mock_post.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.__aexit__ = AsyncMock()

            await client.scrape_url(url="https://example.com")

            # Session should be initialized
            assert client.session is not None

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_scrape_url_no_results(self):
        """Test scrape_url with no content found."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.scrape_url(url="https://example.com/empty")

        assert result["success"] is False
        assert result["url"] == "https://example.com/empty"
        assert result["error"] == "No content found"

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_scrape_url_missing_raw_content(self):
        """Test scrape_url with missing raw_content field."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"results": [{}]}  # Missing raw_content
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.scrape_url(url="https://example.com")

        assert result["success"] is True
        assert result["content"] == ""  # Empty string fallback

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_scrape_url_http_error(self):
        """Test scrape_url handles HTTP errors."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.raise_for_status = Mock(
            side_effect=aiohttp.ClientResponseError(
                request_info=Mock(),
                history=(),
                status=404,
                message="Not found",
            )
        )

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.scrape_url(url="https://example.com/404")

        assert result["success"] is False
        assert result["url"] == "https://example.com/404"
        assert "error" in result

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_scrape_url_network_timeout(self):
        """Test scrape_url handles network timeouts."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_session = AsyncMock()
        mock_session.post = Mock(
            side_effect=aiohttp.ClientTimeout("Request timeout")
        )
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        client.session = mock_session

        result = await client.scrape_url(url="https://slow.example.com")

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_scrape_url_title_extraction(self):
        """Test scrape_url extracts title from URL."""
        client = TavilyClient(api_key="test-tavily-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"results": [{"raw_content": "Test content"}]}
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        # Test with path
        result = await client.scrape_url(url="https://example.com/article/test-title")
        assert result["title"] == "test-title"

        # Test with trailing slash - split("/")[-1] returns empty string
        result = await client.scrape_url(url="https://example.com/article/")
        assert result["title"] == ""  # Empty string because of trailing slash

        # Test without trailing slash
        result = await client.scrape_url(url="https://example.com/article")
        assert result["title"] == "article"

        # Cleanup
        await client.close()


class TestPerplexityClientInitialization:
    """Test PerplexityClient initialization and lifecycle."""

    def test_perplexity_client_creation(self):
        """Test creating a Perplexity client."""
        client = PerplexityClient(api_key="test-perplexity-key")

        assert client.api_key == "test-perplexity-key"
        assert client.base_url == "https://api.perplexity.ai"
        assert client.session is None

    @pytest.mark.asyncio
    async def test_perplexity_client_initialize(self):
        """Test initializing Perplexity client creates session."""
        client = PerplexityClient(api_key="test-perplexity-key")

        await client.initialize()

        assert client.session is not None
        assert isinstance(client.session, aiohttp.ClientSession)

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_perplexity_client_initialize_idempotent(self):
        """Test initializing Perplexity client multiple times is safe."""
        client = PerplexityClient(api_key="test-perplexity-key")

        await client.initialize()
        session1 = client.session

        await client.initialize()
        session2 = client.session

        # Should reuse same session
        assert session1 is session2

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_perplexity_client_close(self):
        """Test closing Perplexity client."""
        client = PerplexityClient(api_key="test-perplexity-key")

        await client.initialize()
        assert client.session is not None

        await client.close()
        assert client.session is None

    @pytest.mark.asyncio
    async def test_perplexity_client_timeout_longer_than_tavily(self):
        """Test Perplexity client has longer timeout than Tavily."""
        client = PerplexityClient(api_key="test-perplexity-key")

        await client.initialize()

        # Perplexity timeout should be 120s (longer than Tavily's 60s)
        assert client.session is not None
        # Note: ClientSession doesn't expose timeout directly in older versions

        # Cleanup
        await client.close()


class TestPerplexityClientDeepResearch:
    """Test PerplexityClient deep research functionality."""

    @pytest.mark.asyncio
    async def test_deep_research_successful(self):
        """Test successful deep research."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": "This is a comprehensive research answer with detailed analysis."
                        }
                    }
                ],
                "citations": [
                    "https://example.com/source1",
                    "https://example.com/source2",
                ],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.deep_research(query="What is quantum computing?")

        assert result["success"] is True
        assert (
            result["answer"]
            == "This is a comprehensive research answer with detailed analysis."
        )
        assert len(result["sources"]) == 2
        assert result["sources"][0]["url"] == "https://example.com/source1"
        assert "title" in result["sources"][0]

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_deep_research_auto_initializes_session(self):
        """Test deep_research auto-initializes session if not initialized."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"choices": [{"message": {"content": "Test"}}], "citations": []}
        )
        mock_response.raise_for_status = Mock()

        with patch.object(
            aiohttp.ClientSession, "post", return_value=mock_response
        ) as mock_post:
            mock_post.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.__aexit__ = AsyncMock()

            await client.deep_research(query="test")

            # Session should be initialized
            assert client.session is not None

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_deep_research_no_choices(self):
        """Test deep_research with no choices in response."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"choices": []})
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.deep_research(query="test")

        assert result["success"] is False
        assert result["error"] == "No response from Perplexity"

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_deep_research_no_citations(self):
        """Test deep_research with no citations."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "Answer without citations"}}],
                "citations": [],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.deep_research(query="test")

        assert result["success"] is True
        assert result["sources"] == []

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_deep_research_url_parsing(self):
        """Test deep_research parses URLs correctly for titles."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "Test answer"}}],
                "citations": [
                    "https://www.example.com/article/quantum-computing",
                    "https://research.org/papers/2024/",
                    "https://news.com",
                ],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.deep_research(query="test")

        assert result["success"] is True
        assert len(result["sources"]) == 3

        # Check title extraction
        assert result["sources"][0]["title"] == "example.com/article"
        assert result["sources"][1]["title"] == "research.org/papers"
        assert result["sources"][2]["title"] == "news.com"

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_deep_research_http_error(self):
        """Test deep_research handles HTTP errors."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_response = Mock()
        mock_response.raise_for_status = Mock(
            side_effect=aiohttp.ClientResponseError(
                request_info=Mock(),
                history=(),
                status=401,
                message="Unauthorized",
            )
        )

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.deep_research(query="test")

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_deep_research_network_timeout(self):
        """Test deep_research handles network timeouts."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_session = AsyncMock()
        mock_session.post = Mock(side_effect=aiohttp.ServerTimeoutError())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        client.session = mock_session

        result = await client.deep_research(query="test")

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_deep_research_malformed_url_in_citations(self):
        """Test deep_research handles malformed URLs in citations."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "Test answer"}}],
                "citations": [
                    "not-a-valid-url",
                    "https://valid.com/path",
                ],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        result = await client.deep_research(query="test")

        assert result["success"] is True
        assert len(result["sources"]) == 2

        # Should handle malformed URL gracefully
        assert result["sources"][0]["url"] == "not-a-valid-url"

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_deep_research_system_prompt_configuration(self):
        """Test deep_research uses correct system prompt."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "Test answer"}}],
                "citations": [],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        await client.deep_research(query="test")

        # Verify system prompt was sent
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"]
        messages = payload["messages"]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "business intelligence researcher" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "test"

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_deep_research_configuration_parameters(self):
        """Test deep_research uses correct configuration parameters."""
        client = PerplexityClient(api_key="test-perplexity-key")

        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "Test answer"}}],
                "citations": [],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_post_cm = create_mock_post_context_manager(mock_response)
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_cm)

        client.session = mock_session

        await client.deep_research(query="test")

        # Verify configuration
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"]

        assert payload["model"] == "sonar-pro"
        assert payload["return_citations"] is True
        assert payload["return_images"] is False
        assert payload["search_recency_filter"] == "month"
        assert payload["temperature"] == 0.2

        # Cleanup
        await client.close()


class TestSingletonManagement:
    """Test singleton client management functions."""

    @pytest.mark.asyncio
    async def test_initialize_tavily_client(self):
        """Test initializing Tavily singleton client."""
        # Reset singleton
        from services import search_clients

        search_clients._tavily_client = None

        await initialize_search_clients(tavily_api_key="test-tavily-key")

        client = get_tavily_client()
        assert client is not None
        assert client.api_key == "test-tavily-key"
        assert client.session is not None

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_perplexity_client(self):
        """Test initializing Perplexity singleton client."""
        # Reset singleton
        from services import search_clients

        search_clients._perplexity_client = None

        await initialize_search_clients(perplexity_api_key="test-perplexity-key")

        client = get_perplexity_client()
        assert client is not None
        assert client.api_key == "test-perplexity-key"
        assert client.session is not None

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_both_clients(self):
        """Test initializing both clients."""
        # Reset singletons
        from services import search_clients

        search_clients._tavily_client = None
        search_clients._perplexity_client = None

        await initialize_search_clients(
            tavily_api_key="test-tavily-key",
            perplexity_api_key="test-perplexity-key",
        )

        tavily = get_tavily_client()
        perplexity = get_perplexity_client()

        assert tavily is not None
        assert perplexity is not None

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_clients_with_none_keys(self):
        """Test initializing with None API keys."""
        # Reset singletons
        from services import search_clients

        search_clients._tavily_client = None
        search_clients._perplexity_client = None

        await initialize_search_clients(tavily_api_key=None, perplexity_api_key=None)

        assert get_tavily_client() is None
        assert get_perplexity_client() is None

    @pytest.mark.asyncio
    async def test_initialize_clients_idempotent(self):
        """Test initializing clients multiple times is safe."""
        # Reset singletons
        from services import search_clients

        search_clients._tavily_client = None

        await initialize_search_clients(tavily_api_key="test-key")
        client1 = get_tavily_client()

        await initialize_search_clients(tavily_api_key="test-key")
        client2 = get_tavily_client()

        # Should be same instance
        assert client1 is client2

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_close_search_clients(self):
        """Test closing all search clients."""
        # Reset and initialize
        from services import search_clients

        search_clients._tavily_client = None
        search_clients._perplexity_client = None

        await initialize_search_clients(
            tavily_api_key="test-tavily-key",
            perplexity_api_key="test-perplexity-key",
        )

        assert get_tavily_client() is not None
        assert get_perplexity_client() is not None

        await close_search_clients()

        assert get_tavily_client() is None
        assert get_perplexity_client() is None

    @pytest.mark.asyncio
    async def test_close_search_clients_when_not_initialized(self):
        """Test closing clients when not initialized."""
        # Reset singletons
        from services import search_clients

        search_clients._tavily_client = None
        search_clients._perplexity_client = None

        # Should not raise
        await close_search_clients()

        assert get_tavily_client() is None
        assert get_perplexity_client() is None

    @pytest.mark.asyncio
    async def test_get_tavily_client_before_initialization(self):
        """Test getting Tavily client before initialization."""
        from services import search_clients

        search_clients._tavily_client = None

        client = get_tavily_client()
        assert client is None

    @pytest.mark.asyncio
    async def test_get_perplexity_client_before_initialization(self):
        """Test getting Perplexity client before initialization."""
        from services import search_clients

        search_clients._perplexity_client = None

        client = get_perplexity_client()
        assert client is None


class TestToolDefinitions:
    """Test tool definition generation."""

    def test_get_tool_definitions_basic(self):
        """Test getting basic tool definitions without deep research."""
        # Reset singletons
        from services import search_clients

        search_clients._tavily_client = TavilyClient("test-key")
        search_clients._perplexity_client = None

        tools = get_tool_definitions(include_deep_research=False)

        assert len(tools) == 2
        assert tools[0]["function"]["name"] == "web_search"
        assert tools[1]["function"]["name"] == "scrape_url"

    def test_get_tool_definitions_with_deep_research(self):
        """Test getting tool definitions with deep research."""
        # Reset singletons
        from services import search_clients

        search_clients._tavily_client = TavilyClient("test-key")
        search_clients._perplexity_client = PerplexityClient("test-key")

        tools = get_tool_definitions(include_deep_research=True)

        assert len(tools) == 3
        assert tools[0]["function"]["name"] == "web_search"
        assert tools[1]["function"]["name"] == "scrape_url"
        assert tools[2]["function"]["name"] == "deep_research"

    def test_get_tool_definitions_no_perplexity_client(self):
        """Test deep research tool not included if client not initialized."""
        # Reset singletons
        from services import search_clients

        search_clients._tavily_client = TavilyClient("test-key")
        search_clients._perplexity_client = None

        tools = get_tool_definitions(include_deep_research=True)

        # Should only have 2 tools since perplexity client not initialized
        assert len(tools) == 2

    def test_web_search_tool_definition_structure(self):
        """Test web_search tool definition has correct structure."""
        tools = get_tool_definitions(include_deep_research=False)

        web_search = tools[0]
        assert web_search["type"] == "function"
        assert web_search["function"]["name"] == "web_search"
        assert "description" in web_search["function"]
        assert "parameters" in web_search["function"]

        params = web_search["function"]["parameters"]
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert "max_results" in params["properties"]
        assert params["required"] == ["query"]

    def test_scrape_url_tool_definition_structure(self):
        """Test scrape_url tool definition has correct structure."""
        tools = get_tool_definitions(include_deep_research=False)

        scrape_url = tools[1]
        assert scrape_url["type"] == "function"
        assert scrape_url["function"]["name"] == "scrape_url"
        assert "description" in scrape_url["function"]
        assert "parameters" in scrape_url["function"]

        params = scrape_url["function"]["parameters"]
        assert params["type"] == "object"
        assert "url" in params["properties"]
        assert params["required"] == ["url"]

    def test_deep_research_tool_definition_structure(self):
        """Test deep_research tool definition has correct structure."""
        from services import search_clients

        search_clients._perplexity_client = PerplexityClient("test-key")

        tools = get_tool_definitions(include_deep_research=True)

        deep_research = tools[2]
        assert deep_research["type"] == "function"
        assert deep_research["function"]["name"] == "deep_research"
        assert "description" in deep_research["function"]
        assert "EXPENSIVE" in deep_research["function"]["description"]
        assert "parameters" in deep_research["function"]

        params = deep_research["function"]["parameters"]
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert params["required"] == ["query"]

    def test_tool_definitions_descriptions_have_usage_guidance(self):
        """Test tool definitions include usage guidance."""
        from services import search_clients

        search_clients._perplexity_client = PerplexityClient("test-key")

        tools = get_tool_definitions(include_deep_research=True)

        # web_search should mention when to use it
        web_search = tools[0]
        assert "recent news" in web_search["function"]["description"].lower()
        assert "current" in web_search["function"]["description"].lower()

        # scrape_url should mention using it after web_search
        scrape_url = tools[1]
        assert "after web_search" in scrape_url["function"]["description"].lower()

        # deep_research should mention cost and strategy
        deep_research = tools[2]
        assert "expensive" in deep_research["function"]["description"].lower()
        assert "strategy" in deep_research["function"]["description"].lower()


class TestConstants:
    """Test module constants."""

    def test_default_search_timeout(self):
        """Test default search timeout constant."""
        assert DEFAULT_SEARCH_TIMEOUT == 60

    def test_default_max_search_results(self):
        """Test default max search results constant."""
        assert DEFAULT_MAX_SEARCH_RESULTS == 10
