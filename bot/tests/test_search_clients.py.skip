"""
Comprehensive tests for search_clients.py

Tests both TavilyClient and PerplexityClient classes including:
- Client initialization and cleanup
- Successful API calls with mock responses
- Error handling (API failures, timeouts, malformed responses)
- Module-level functions (initialize_search_clients, close_search_clients, get_tool_definitions)
- Edge cases and boundary conditions
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from bot_types import DeepResearchResult, WebScrapeResult, WebSearchResult
from services.search_clients import (
    DEFAULT_MAX_SEARCH_RESULTS,
    DEFAULT_SEARCH_TIMEOUT,
    PerplexityClient,
    TavilyClient,
    _get_deep_research_tool,
    _get_scrape_url_tool,
    _get_web_search_tool,
    close_search_clients,
    get_perplexity_client,
    get_tavily_client,
    get_tool_definitions,
    initialize_search_clients,
)


# TDD Factory Patterns for Search Clients Testing
class MockHttpResponseFactory:
    """Factory for creating mock HTTP responses"""

    @staticmethod
    def create_successful_search_response(num_results: int = 3) -> Mock:
        """Create successful Tavily search response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {
                        "title": f"Result {i}",
                        "url": f"https://example.com/page{i}",
                        "content": f"This is result {i} content snippet",
                    }
                    for i in range(num_results)
                ]
            }
        )
        mock_response.raise_for_status = Mock()
        return mock_response

    @staticmethod
    def create_empty_search_response() -> Mock:
        """Create empty Tavily search response (no results)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = Mock()
        return mock_response

    @staticmethod
    def create_successful_scrape_response(content: str = "Scraped content") -> Mock:
        """Create successful Tavily scrape response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {
                        "raw_content": content,
                    }
                ]
            }
        )
        mock_response.raise_for_status = Mock()
        return mock_response

    @staticmethod
    def create_empty_scrape_response() -> Mock:
        """Create empty Tavily scrape response (no content found)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.raise_for_status = Mock()
        return mock_response

    @staticmethod
    def create_successful_perplexity_response(
        answer: str = "Research answer", citations: list[str] | None = None
    ) -> Mock:
        """Create successful Perplexity deep research response"""
        if citations is None:
            citations = [
                "https://example.com/source1",
                "https://techblog.com/article",
            ]
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [{"message": {"content": answer}}],
                "citations": citations,
            }
        )
        mock_response.raise_for_status = Mock()
        return mock_response

    @staticmethod
    def create_empty_perplexity_response() -> Mock:
        """Create empty Perplexity response (no choices)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"choices": []})
        mock_response.raise_for_status = Mock()
        return mock_response

    @staticmethod
    def create_http_error_response(status_code: int = 500) -> Mock:
        """Create HTTP error response"""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.raise_for_status = Mock(
            side_effect=aiohttp.ClientResponseError(
                request_info=Mock(),
                history=(),
                status=status_code,
                message=f"HTTP {status_code} Error",
            )
        )
        return mock_response

    @staticmethod
    def create_timeout_error() -> Exception:
        """Create timeout error"""
        return aiohttp.ServerTimeoutError("Request timeout")

    @staticmethod
    def create_connection_error() -> Exception:
        """Create connection error"""
        return aiohttp.ClientConnectionError("Connection failed")

    @staticmethod
    def create_malformed_json_response() -> Mock:
        """Create response with malformed JSON"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            side_effect=json.JSONDecodeError("msg", "doc", 0)
        )
        mock_response.raise_for_status = Mock()
        return mock_response


class SearchClientTestDataFactory:
    """Factory for creating test data"""

    @staticmethod
    def create_web_search_results(count: int = 3) -> list[WebSearchResult]:
        """Create expected web search results"""
        return [
            {
                "title": f"Result {i}",
                "url": f"https://example.com/page{i}",
                "snippet": f"This is result {i} content snippet",
            }
            for i in range(count)
        ]

    @staticmethod
    def create_web_scrape_result(
        success: bool = True,
        url: str = "https://example.com",
        content: str = "Scraped content",
    ) -> WebScrapeResult:
        """Create expected web scrape result"""
        if success:
            return {
                "success": True,
                "url": url,
                "title": url.split("/")[-1],
                "content": content,
            }
        return {"success": False, "url": url, "error": "No content found"}

    @staticmethod
    def create_deep_research_result(
        success: bool = True, answer: str = "Research answer"
    ) -> DeepResearchResult:
        """Create expected deep research result"""
        if success:
            return {
                "success": True,
                "answer": answer,
                "sources": [
                    {"url": "https://example.com/source1", "title": "example.com"},
                    {"url": "https://techblog.com/article", "title": "techblog.com"},
                ],
            }
        return {"success": False, "error": "No response from Perplexity"}


@pytest.fixture
def tavily_api_key():
    """Test Tavily API key"""
    return "test-tavily-key"


@pytest.fixture
def perplexity_api_key():
    """Test Perplexity API key"""
    return "test-perplexity-key"


@pytest.fixture
def tavily_client(tavily_api_key):
    """Create TavilyClient for testing"""
    return TavilyClient(tavily_api_key)


@pytest.fixture
def perplexity_client(perplexity_api_key):
    """Create PerplexityClient for testing"""
    return PerplexityClient(perplexity_api_key)


@pytest.fixture
def mock_session():
    """Create mock aiohttp ClientSession"""
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False
    return session


class TestTavilyClient:
    """Tests for TavilyClient"""

    def test_init(self, tavily_client, tavily_api_key):
        """Test TavilyClient initialization"""
        # Arrange / Act
        # (client created in fixture)

        # Assert
        assert tavily_client.api_key == tavily_api_key
        assert tavily_client.base_url == "https://api.tavily.com"
        assert tavily_client.session is None

    @pytest.mark.asyncio
    async def test_initialize(self, tavily_client):
        """Test TavilyClient session initialization"""
        # Arrange / Act
        await tavily_client.initialize()

        # Assert
        assert tavily_client.session is not None
        assert isinstance(tavily_client.session, aiohttp.ClientSession)

        # Cleanup
        await tavily_client.close()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, tavily_client):
        """Test that initialize() is idempotent (doesn't create multiple sessions)"""
        # Arrange
        await tavily_client.initialize()
        first_session = tavily_client.session

        # Act
        await tavily_client.initialize()
        second_session = tavily_client.session

        # Assert
        assert first_session is second_session

        # Cleanup
        await tavily_client.close()

    @pytest.mark.asyncio
    async def test_close(self, tavily_client, mock_session):
        """Test TavilyClient session cleanup"""
        # Arrange
        tavily_client.session = mock_session

        # Act
        await tavily_client.close()

        # Assert
        mock_session.close.assert_called_once()
        assert tavily_client.session is None

    @pytest.mark.asyncio
    async def test_close_when_no_session(self, tavily_client):
        """Test close() when no session exists (no error)"""
        # Arrange
        assert tavily_client.session is None

        # Act / Assert (should not raise)
        await tavily_client.close()

    @pytest.mark.asyncio
    async def test_search_success(self, tavily_client, mock_session):
        """Test successful web search"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_successful_search_response(3)
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        results = await tavily_client.search("test query")

        # Assert
        assert len(results) == 3
        assert results[0]["title"] == "Result 0"
        assert results[0]["url"] == "https://example.com/page0"
        assert results[0]["snippet"] == "This is result 0 content snippet"
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_auto_initialize(self, tavily_client):
        """Test search auto-initializes session if not initialized"""
        # Arrange
        assert tavily_client.session is None
        mock_session = AsyncMock()
        mock_response = MockHttpResponseFactory.create_successful_search_response(2)
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Mock initialize to set the session
        async def mock_initialize():
            tavily_client.session = mock_session

        with patch.object(
            tavily_client, "initialize", side_effect=mock_initialize
        ) as mock_initialize_spy:
            # Act
            await tavily_client.search("test query")

            # Assert
            mock_initialize_spy.assert_called_once()

        # Cleanup
        if tavily_client.session:
            await tavily_client.close()

    @pytest.mark.asyncio
    async def test_search_with_max_results(self, tavily_client, mock_session):
        """Test search with custom max_results parameter"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_successful_search_response(5)
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        results = await tavily_client.search("test query", max_results=5)

        # Assert
        assert len(results) == 5
        call_args = mock_session.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["max_results"] == 5

    @pytest.mark.asyncio
    async def test_search_empty_results(self, tavily_client, mock_session):
        """Test search with no results"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_empty_search_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        results = await tavily_client.search("nonexistent query")

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_search_http_error(self, tavily_client, mock_session):
        """Test search with HTTP error"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_http_error_response(500)
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        results = await tavily_client.search("test query")

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_search_timeout_error(self, tavily_client, mock_session):
        """Test search with timeout error"""
        # Arrange
        tavily_client.session = mock_session
        mock_session.post.side_effect = MockHttpResponseFactory.create_timeout_error()

        # Act
        results = await tavily_client.search("test query")

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_search_connection_error(self, tavily_client, mock_session):
        """Test search with connection error"""
        # Arrange
        tavily_client.session = mock_session
        mock_session.post.side_effect = (
            MockHttpResponseFactory.create_connection_error()
        )

        # Act
        results = await tavily_client.search("test query")

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_search_malformed_json(self, tavily_client, mock_session):
        """Test search with malformed JSON response"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_malformed_json_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        results = await tavily_client.search("test query")

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_scrape_url_success(self, tavily_client, mock_session):
        """Test successful URL scraping"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_successful_scrape_response(
            "This is the full page content"
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response
        test_url = "https://example.com/article"

        # Act
        result = await tavily_client.scrape_url(test_url)

        # Assert
        assert result["success"] is True
        assert result["url"] == test_url
        assert result["content"] == "This is the full page content"
        assert "title" in result
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_url_auto_initialize(self, tavily_client):
        """Test scrape_url auto-initializes session if not initialized"""
        # Arrange
        assert tavily_client.session is None
        mock_session = AsyncMock()
        mock_response = MockHttpResponseFactory.create_successful_scrape_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Mock initialize to set the session
        async def mock_initialize():
            tavily_client.session = mock_session

        with patch.object(
            tavily_client, "initialize", side_effect=mock_initialize
        ) as mock_initialize_spy:
            # Act
            await tavily_client.scrape_url("https://example.com")

            # Assert
            mock_initialize_spy.assert_called_once()

        # Cleanup
        if tavily_client.session:
            await tavily_client.close()

    @pytest.mark.asyncio
    async def test_scrape_url_no_content(self, tavily_client, mock_session):
        """Test scrape_url with no content found"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_empty_scrape_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        test_url = "https://example.com/notfound"

        # Act
        result = await tavily_client.scrape_url(test_url)

        # Assert
        assert result["success"] is False
        assert result["url"] == test_url
        assert "error" in result
        assert result["error"] == "No content found"

    @pytest.mark.asyncio
    async def test_scrape_url_http_error(self, tavily_client, mock_session):
        """Test scrape_url with HTTP error"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_http_error_response(404)
        mock_session.post.return_value.__aenter__.return_value = mock_response
        test_url = "https://example.com/404"

        # Act
        result = await tavily_client.scrape_url(test_url)

        # Assert
        assert result["success"] is False
        assert result["url"] == test_url
        assert "error" in result

    @pytest.mark.asyncio
    async def test_scrape_url_timeout_error(self, tavily_client, mock_session):
        """Test scrape_url with timeout error"""
        # Arrange
        tavily_client.session = mock_session
        mock_session.post.side_effect = MockHttpResponseFactory.create_timeout_error()
        test_url = "https://example.com/slow"

        # Act
        result = await tavily_client.scrape_url(test_url)

        # Assert
        assert result["success"] is False
        assert result["url"] == test_url
        assert "error" in result


class TestPerplexityClient:
    """Tests for PerplexityClient"""

    def test_init(self, perplexity_client, perplexity_api_key):
        """Test PerplexityClient initialization"""
        # Arrange / Act
        # (client created in fixture)

        # Assert
        assert perplexity_client.api_key == perplexity_api_key
        assert perplexity_client.base_url == "https://api.perplexity.ai"
        assert perplexity_client.session is None

    @pytest.mark.asyncio
    async def test_initialize(self, perplexity_client):
        """Test PerplexityClient session initialization"""
        # Arrange / Act
        await perplexity_client.initialize()

        # Assert
        assert perplexity_client.session is not None
        assert isinstance(perplexity_client.session, aiohttp.ClientSession)

        # Cleanup
        await perplexity_client.close()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, perplexity_client):
        """Test that initialize() is idempotent"""
        # Arrange
        await perplexity_client.initialize()
        first_session = perplexity_client.session

        # Act
        await perplexity_client.initialize()
        second_session = perplexity_client.session

        # Assert
        assert first_session is second_session

        # Cleanup
        await perplexity_client.close()

    @pytest.mark.asyncio
    async def test_close(self, perplexity_client, mock_session):
        """Test PerplexityClient session cleanup"""
        # Arrange
        perplexity_client.session = mock_session

        # Act
        await perplexity_client.close()

        # Assert
        mock_session.close.assert_called_once()
        assert perplexity_client.session is None

    @pytest.mark.asyncio
    async def test_close_when_no_session(self, perplexity_client):
        """Test close() when no session exists"""
        # Arrange
        assert perplexity_client.session is None

        # Act / Assert (should not raise)
        await perplexity_client.close()

    @pytest.mark.asyncio
    async def test_deep_research_success(self, perplexity_client, mock_session):
        """Test successful deep research"""
        # Arrange
        perplexity_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_successful_perplexity_response(
            answer="Comprehensive research answer",
            citations=["https://example.com/source1", "https://techblog.com/article"],
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        result = await perplexity_client.deep_research("What is quantum computing?")

        # Assert
        assert result["success"] is True
        assert result["answer"] == "Comprehensive research answer"
        assert len(result["sources"]) == 2
        assert result["sources"][0]["url"] == "https://example.com/source1"
        assert "title" in result["sources"][0]
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_deep_research_auto_initialize(self, perplexity_client):
        """Test deep_research auto-initializes session if not initialized"""
        # Arrange
        assert perplexity_client.session is None
        mock_session = AsyncMock()
        mock_response = MockHttpResponseFactory.create_successful_perplexity_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Mock initialize to set the session
        async def mock_initialize():
            perplexity_client.session = mock_session

        with patch.object(
            perplexity_client, "initialize", side_effect=mock_initialize
        ) as mock_initialize_spy:
            # Act
            await perplexity_client.deep_research("test query")

            # Assert
            mock_initialize_spy.assert_called_once()

        # Cleanup
        if perplexity_client.session:
            await perplexity_client.close()

    @pytest.mark.asyncio
    async def test_deep_research_no_choices(self, perplexity_client, mock_session):
        """Test deep research with no choices in response"""
        # Arrange
        perplexity_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_empty_perplexity_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        result = await perplexity_client.deep_research("test query")

        # Assert
        assert result["success"] is False
        assert "error" in result
        assert result["error"] == "No response from Perplexity"

    @pytest.mark.asyncio
    async def test_deep_research_http_error(self, perplexity_client, mock_session):
        """Test deep research with HTTP error"""
        # Arrange
        perplexity_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_http_error_response(500)
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        result = await perplexity_client.deep_research("test query")

        # Assert
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_deep_research_timeout_error(self, perplexity_client, mock_session):
        """Test deep research with timeout error"""
        # Arrange
        perplexity_client.session = mock_session
        mock_session.post.side_effect = MockHttpResponseFactory.create_timeout_error()

        # Act
        result = await perplexity_client.deep_research("test query")

        # Assert
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_deep_research_connection_error(
        self, perplexity_client, mock_session
    ):
        """Test deep research with connection error"""
        # Arrange
        perplexity_client.session = mock_session
        mock_session.post.side_effect = (
            MockHttpResponseFactory.create_connection_error()
        )

        # Act
        result = await perplexity_client.deep_research("test query")

        # Assert
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_deep_research_source_parsing(self, perplexity_client, mock_session):
        """Test deep research source title parsing from URLs"""
        # Arrange
        perplexity_client.session = mock_session
        citations = [
            "https://example.com",
            "https://www.techblog.com/article/quantum-computing",
            "https://research.org/papers/science",
        ]
        mock_response = MockHttpResponseFactory.create_successful_perplexity_response(
            citations=citations
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        result = await perplexity_client.deep_research("test query")

        # Assert
        assert result["success"] is True
        assert len(result["sources"]) == 3
        # Test various URL parsing scenarios
        assert result["sources"][0]["title"] == "example.com"
        assert result["sources"][1]["title"] == "techblog.com/article"
        assert result["sources"][2]["title"] == "research.org/papers"

    @pytest.mark.asyncio
    async def test_deep_research_request_payload(self, perplexity_client, mock_session):
        """Test deep research sends correct request payload"""
        # Arrange
        perplexity_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_successful_perplexity_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        test_query = "What are the latest AI trends?"

        # Act
        await perplexity_client.deep_research(test_query)

        # Assert
        call_args = mock_session.post.call_args
        payload = call_args.kwargs["json"]
        headers = call_args.kwargs["headers"]

        # Verify payload structure
        assert payload["model"] == "sonar-pro"
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == test_query
        assert payload["return_citations"] is True
        assert payload["return_images"] is False
        assert payload["search_recency_filter"] == "month"
        assert payload["temperature"] == 0.2

        # Verify headers
        assert headers["Authorization"] == f"Bearer {perplexity_client.api_key}"
        assert headers["Content-Type"] == "application/json"


class TestModuleLevelFunctions:
    """Tests for module-level singleton functions"""

    @pytest.mark.asyncio
    async def test_initialize_search_clients_tavily_only(self, tavily_api_key):
        """Test initialize_search_clients with Tavily only"""
        # Arrange / Act
        await initialize_search_clients(tavily_api_key=tavily_api_key)

        # Assert
        tavily_client = get_tavily_client()
        perplexity_client = get_perplexity_client()
        assert tavily_client is not None
        assert perplexity_client is None

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_search_clients_perplexity_only(self, perplexity_api_key):
        """Test initialize_search_clients with Perplexity only"""
        # Arrange / Act
        await initialize_search_clients(perplexity_api_key=perplexity_api_key)

        # Assert
        tavily_client = get_tavily_client()
        perplexity_client = get_perplexity_client()
        assert tavily_client is None
        assert perplexity_client is not None

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_search_clients_both(
        self, tavily_api_key, perplexity_api_key
    ):
        """Test initialize_search_clients with both clients"""
        # Arrange / Act
        await initialize_search_clients(
            tavily_api_key=tavily_api_key, perplexity_api_key=perplexity_api_key
        )

        # Assert
        tavily_client = get_tavily_client()
        perplexity_client = get_perplexity_client()
        assert tavily_client is not None
        assert perplexity_client is not None

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_search_clients_idempotent(self, tavily_api_key):
        """Test initialize_search_clients is idempotent (doesn't recreate existing clients)"""
        # Arrange
        await initialize_search_clients(tavily_api_key=tavily_api_key)
        first_client = get_tavily_client()

        # Act
        await initialize_search_clients(tavily_api_key=tavily_api_key)
        second_client = get_tavily_client()

        # Assert
        assert first_client is second_client

        # Cleanup
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_initialize_search_clients_none(self):
        """Test initialize_search_clients with no API keys (no-op)"""
        # Arrange / Act
        await initialize_search_clients()

        # Assert
        tavily_client = get_tavily_client()
        perplexity_client = get_perplexity_client()
        assert tavily_client is None
        assert perplexity_client is None

    @pytest.mark.asyncio
    async def test_close_search_clients(self, tavily_api_key, perplexity_api_key):
        """Test close_search_clients closes all clients"""
        # Arrange
        await initialize_search_clients(
            tavily_api_key=tavily_api_key, perplexity_api_key=perplexity_api_key
        )
        assert get_tavily_client() is not None
        assert get_perplexity_client() is not None

        # Act
        await close_search_clients()

        # Assert
        assert get_tavily_client() is None
        assert get_perplexity_client() is None

    @pytest.mark.asyncio
    async def test_close_search_clients_when_none_exist(self):
        """Test close_search_clients when no clients exist (no error)"""
        # Arrange
        assert get_tavily_client() is None
        assert get_perplexity_client() is None

        # Act / Assert (should not raise)
        await close_search_clients()

    @pytest.mark.asyncio
    async def test_get_tavily_client_before_initialize(self):
        """Test get_tavily_client returns None before initialization"""
        # Arrange / Act
        client = get_tavily_client()

        # Assert
        assert client is None

    @pytest.mark.asyncio
    async def test_get_perplexity_client_before_initialize(self):
        """Test get_perplexity_client returns None before initialization"""
        # Arrange / Act
        client = get_perplexity_client()

        # Assert
        assert client is None


class TestToolDefinitions:
    """Tests for tool definition functions"""

    def test_get_tool_definitions_default(self):
        """Test get_tool_definitions returns web_search and scrape_url by default"""
        # Arrange / Act
        tools = get_tool_definitions()

        # Assert
        assert len(tools) == 2
        assert tools[0]["function"]["name"] == "web_search"
        assert tools[1]["function"]["name"] == "scrape_url"

    def test_get_tool_definitions_without_deep_research(self):
        """Test get_tool_definitions with include_deep_research=False"""
        # Arrange / Act
        tools = get_tool_definitions(include_deep_research=False)

        # Assert
        assert len(tools) == 2
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "deep_research" not in tool_names

    @pytest.mark.asyncio
    async def test_get_tool_definitions_with_deep_research(self, perplexity_api_key):
        """Test get_tool_definitions with include_deep_research=True"""
        # Arrange
        await initialize_search_clients(perplexity_api_key=perplexity_api_key)

        # Act
        tools = get_tool_definitions(include_deep_research=True)

        # Assert
        assert len(tools) == 3
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "web_search" in tool_names
        assert "scrape_url" in tool_names
        assert "deep_research" in tool_names

        # Cleanup
        await close_search_clients()

    def test_get_tool_definitions_without_perplexity_client(self):
        """Test get_tool_definitions doesn't include deep_research if client not initialized"""
        # Arrange
        assert get_perplexity_client() is None

        # Act
        tools = get_tool_definitions(include_deep_research=True)

        # Assert
        assert len(tools) == 2  # Only web_search and scrape_url
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "deep_research" not in tool_names

    def test_web_search_tool_structure(self):
        """Test web_search tool definition structure"""
        # Arrange / Act
        tool = _get_web_search_tool()

        # Assert
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "web_search"
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]
        assert tool["function"]["parameters"]["type"] == "object"
        assert "query" in tool["function"]["parameters"]["properties"]
        assert "max_results" in tool["function"]["parameters"]["properties"]
        assert "query" in tool["function"]["parameters"]["required"]

    def test_scrape_url_tool_structure(self):
        """Test scrape_url tool definition structure"""
        # Arrange / Act
        tool = _get_scrape_url_tool()

        # Assert
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "scrape_url"
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]
        assert tool["function"]["parameters"]["type"] == "object"
        assert "url" in tool["function"]["parameters"]["properties"]
        assert "url" in tool["function"]["parameters"]["required"]

    def test_deep_research_tool_structure(self):
        """Test deep_research tool definition structure"""
        # Arrange / Act
        tool = _get_deep_research_tool()

        # Assert
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "deep_research"
        assert "description" in tool["function"]
        assert "EXPENSIVE" in tool["function"]["description"]  # Cost warning
        assert "parameters" in tool["function"]
        assert tool["function"]["parameters"]["type"] == "object"
        assert "query" in tool["function"]["parameters"]["properties"]
        assert "query" in tool["function"]["parameters"]["required"]


class TestConstants:
    """Tests for module constants"""

    def test_default_search_timeout(self):
        """Test DEFAULT_SEARCH_TIMEOUT constant"""
        assert DEFAULT_SEARCH_TIMEOUT == 60

    def test_default_max_search_results(self):
        """Test DEFAULT_MAX_SEARCH_RESULTS constant"""
        assert DEFAULT_MAX_SEARCH_RESULTS == 10


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_tavily_search_with_zero_max_results(
        self, tavily_client, mock_session
    ):
        """Test search with max_results=0"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_empty_search_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        results = await tavily_client.search("test query", max_results=0)

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_tavily_search_with_large_max_results(
        self, tavily_client, mock_session
    ):
        """Test search with very large max_results"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_successful_search_response(100)
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        results = await tavily_client.search("test query", max_results=1000)

        # Assert
        assert len(results) == 100
        call_args = mock_session.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["max_results"] == 1000

    @pytest.mark.asyncio
    async def test_tavily_search_with_empty_query(self, tavily_client, mock_session):
        """Test search with empty query string"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_empty_search_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        results = await tavily_client.search("")

        # Assert
        # Should still make API call (API will handle validation)
        mock_session.post.assert_called_once()
        assert results == []

    @pytest.mark.asyncio
    async def test_tavily_scrape_with_empty_url(self, tavily_client, mock_session):
        """Test scrape_url with empty URL"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_empty_scrape_response()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        result = await tavily_client.scrape_url("")

        # Assert
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_perplexity_research_with_empty_query(
        self, perplexity_client, mock_session
    ):
        """Test deep_research with empty query string"""
        # Arrange
        perplexity_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_successful_perplexity_response(
            answer="Empty query response"
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        result = await perplexity_client.deep_research("")

        # Assert
        # Should still make API call
        mock_session.post.assert_called_once()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_perplexity_research_with_no_citations(
        self, perplexity_client, mock_session
    ):
        """Test deep_research when API returns no citations"""
        # Arrange
        perplexity_client.session = mock_session
        mock_response = MockHttpResponseFactory.create_successful_perplexity_response(
            citations=[]
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        result = await perplexity_client.deep_research("test query")

        # Assert
        assert result["success"] is True
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_perplexity_source_parsing_with_invalid_url(
        self, perplexity_client, mock_session
    ):
        """Test deep_research source parsing with malformed URLs"""
        # Arrange
        perplexity_client.session = mock_session
        citations = ["not-a-url", "also:invalid", "https://valid.com"]
        mock_response = MockHttpResponseFactory.create_successful_perplexity_response(
            citations=citations
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        result = await perplexity_client.deep_research("test query")

        # Assert
        assert result["success"] is True
        assert len(result["sources"]) == 3
        # Invalid URLs should still get some title (fallback to truncated URL)
        for source in result["sources"]:
            assert "title" in source
            assert "url" in source

    @pytest.mark.asyncio
    async def test_perplexity_source_parsing_with_urlparse_exception(
        self, perplexity_client, mock_session
    ):
        """Test deep_research handles urlparse exceptions with fallback"""
        # Arrange
        perplexity_client.session = mock_session
        # Very long URL that triggers fallback on exception
        long_url = "https://example.com/" + "a" * 100
        citations = [long_url]
        mock_response = MockHttpResponseFactory.create_successful_perplexity_response(
            citations=citations
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Mock urlparse to raise an exception (patching at import location)
        with patch("urllib.parse.urlparse", side_effect=Exception("Parse error")):
            # Act
            result = await perplexity_client.deep_research("test query")

        # Assert
        assert result["success"] is True
        assert len(result["sources"]) == 1
        # Should use fallback: truncated URL (first 50 chars)
        assert result["sources"][0]["title"] == long_url[:50]
        assert result["sources"][0]["url"] == long_url

    @pytest.mark.asyncio
    async def test_tavily_search_partial_results(self, tavily_client, mock_session):
        """Test search when some results are missing fields"""
        # Arrange
        tavily_client.session = mock_session
        mock_response = Mock()
        mock_response.status_code = 200
        # Some results missing title or content
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {
                        "title": "Result 1",
                        "url": "https://example.com/1",
                        "content": "Content 1",
                    },
                    {"url": "https://example.com/2"},  # Missing title and content
                    {
                        "title": "Result 3",
                        "url": "https://example.com/3",
                    },  # Missing content
                ]
            }
        )
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        # Act
        results = await tavily_client.search("test query")

        # Assert
        assert len(results) == 3
        assert results[0]["title"] == "Result 1"
        assert results[1]["title"] == ""  # Default empty string
        assert results[1]["snippet"] == ""  # Default empty string
        assert results[2]["snippet"] == ""  # Default empty string
