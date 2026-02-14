"""Tests for cached search functions in search_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from profiler.services.search_service import cached_scrape_url, cached_web_search


@pytest.fixture
def mock_cache():
    """Create a mock cache service."""
    return MagicMock()


@pytest.fixture
def mock_tavily_client():
    """Create a mock Tavily client."""
    return MagicMock()


class TestCachedWebSearch:
    """Tests for cached_web_search function."""

    @pytest.mark.asyncio
    async def test_returns_cached_results_on_hit(self, mock_cache):
        """Test that cached results are returned on cache hit."""
        cached_results = [
            {"title": "Result 1", "url": "https://example1.com", "snippet": "Snippet 1"},
            {"title": "Result 2", "url": "https://example2.com", "snippet": "Snippet 2"},
        ]
        mock_cache.get_search_results.return_value = {"results": cached_results}

        with patch(
            "profiler.services.search_service.get_tavily_cache", return_value=mock_cache
        ):
            results = await cached_web_search("test query", max_results=2)

        assert results == cached_results
        mock_cache.get_search_results.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_fetches_and_caches_on_miss(self, mock_cache, mock_tavily_client):
        """Test that results are fetched and cached on cache miss."""
        mock_cache.get_search_results.return_value = None
        mock_tavily_client.search.return_value = {
            "results": [
                {"title": "Result 1", "url": "https://example.com", "content": "Content"}
            ]
        }

        with (
            patch(
                "profiler.services.search_service.get_tavily_cache",
                return_value=mock_cache,
            ),
            patch(
                "profiler.services.search_service.get_tavily_client",
                return_value=mock_tavily_client,
            ),
        ):
            results = await cached_web_search("test query", max_results=5)

        assert len(results) == 1
        assert results[0]["title"] == "Result 1"
        mock_cache.save_search_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_list_response_format(self, mock_cache, mock_tavily_client):
        """Test handling of list response format from Tavily."""
        mock_cache.get_search_results.return_value = None
        mock_tavily_client.search.return_value = [
            {"title": "Result 1", "url": "https://example.com", "snippet": "Snippet"}
        ]

        with (
            patch(
                "profiler.services.search_service.get_tavily_cache",
                return_value=mock_cache,
            ),
            patch(
                "profiler.services.search_service.get_tavily_client",
                return_value=mock_tavily_client,
            ),
        ):
            results = await cached_web_search("test query")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_client(self, mock_cache):
        """Test that empty list is returned when client unavailable."""
        mock_cache.get_search_results.return_value = None

        with (
            patch(
                "profiler.services.search_service.get_tavily_cache",
                return_value=mock_cache,
            ),
            patch(
                "profiler.services.search_service.get_tavily_client", return_value=None
            ),
        ):
            results = await cached_web_search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_search_error(self, mock_cache, mock_tavily_client):
        """Test that empty list is returned on search error."""
        mock_cache.get_search_results.return_value = None
        mock_tavily_client.search.side_effect = Exception("API error")

        with (
            patch(
                "profiler.services.search_service.get_tavily_cache",
                return_value=mock_cache,
            ),
            patch(
                "profiler.services.search_service.get_tavily_client",
                return_value=mock_tavily_client,
            ),
        ):
            results = await cached_web_search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_respects_max_results_from_cache(self, mock_cache):
        """Test that max_results is respected when returning cached results."""
        cached_results = [
            {"title": f"Result {i}", "url": f"https://example{i}.com", "snippet": f"Snippet {i}"}
            for i in range(10)
        ]
        mock_cache.get_search_results.return_value = {"results": cached_results}

        with patch(
            "profiler.services.search_service.get_tavily_cache", return_value=mock_cache
        ):
            results = await cached_web_search("test query", max_results=3)

        assert len(results) == 3


class TestCachedScrapeUrl:
    """Tests for cached_scrape_url function."""

    @pytest.mark.asyncio
    async def test_returns_cached_content_on_hit(self, mock_cache):
        """Test that cached content is returned on cache hit."""
        mock_cache.get_scraped_content.return_value = {
            "content": "Cached page content",
            "title": "Cached Title",
        }

        with patch(
            "profiler.services.search_service.get_tavily_cache", return_value=mock_cache
        ):
            result = await cached_scrape_url("https://example.com")

        assert result["success"] is True
        assert result["content"] == "Cached page content"
        assert result["title"] == "Cached Title"
        assert result["from_cache"] is True

    @pytest.mark.asyncio
    async def test_fetches_and_caches_on_miss(self, mock_cache, mock_tavily_client):
        """Test that content is fetched and cached on cache miss."""
        mock_cache.get_scraped_content.return_value = None
        mock_tavily_client.extract.return_value = {
            "results": [{"raw_content": "New content", "title": "New Title"}]
        }

        with (
            patch(
                "profiler.services.search_service.get_tavily_cache",
                return_value=mock_cache,
            ),
            patch(
                "profiler.services.search_service.get_tavily_client",
                return_value=mock_tavily_client,
            ),
        ):
            result = await cached_scrape_url("https://example.com")

        assert result["success"] is True
        assert result["content"] == "New content"
        assert result["from_cache"] is False
        mock_cache.save_scraped_content.assert_called_once_with(
            "https://example.com", "New content", "New Title"
        )

    @pytest.mark.asyncio
    async def test_returns_error_on_no_client(self, mock_cache):
        """Test that error is returned when client unavailable."""
        mock_cache.get_scraped_content.return_value = None

        with (
            patch(
                "profiler.services.search_service.get_tavily_cache",
                return_value=mock_cache,
            ),
            patch(
                "profiler.services.search_service.get_tavily_client", return_value=None
            ),
        ):
            result = await cached_scrape_url("https://example.com")

        assert result["success"] is False
        assert "not available" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_error_on_empty_results(self, mock_cache, mock_tavily_client):
        """Test that error is returned when no content extracted."""
        mock_cache.get_scraped_content.return_value = None
        mock_tavily_client.extract.return_value = {"results": []}

        with (
            patch(
                "profiler.services.search_service.get_tavily_cache",
                return_value=mock_cache,
            ),
            patch(
                "profiler.services.search_service.get_tavily_client",
                return_value=mock_tavily_client,
            ),
        ):
            result = await cached_scrape_url("https://example.com")

        assert result["success"] is False
        assert "No content" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_error_on_extract_exception(
        self, mock_cache, mock_tavily_client
    ):
        """Test that error is returned on extraction exception."""
        mock_cache.get_scraped_content.return_value = None
        mock_tavily_client.extract.side_effect = Exception("API error")

        with (
            patch(
                "profiler.services.search_service.get_tavily_cache",
                return_value=mock_cache,
            ),
            patch(
                "profiler.services.search_service.get_tavily_client",
                return_value=mock_tavily_client,
            ),
        ):
            result = await cached_scrape_url("https://example.com")

        assert result["success"] is False
        assert "API error" in result["error"]
