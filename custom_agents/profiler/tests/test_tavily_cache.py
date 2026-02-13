"""Tests for Tavily cache service."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from profiler.services.tavily_cache import TavilyCacheService, get_tavily_cache


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    return MagicMock()


@pytest.fixture
def cache_service(mock_s3_client):
    """Create a cache service with mocked S3."""
    service = TavilyCacheService()
    service._s3_client = mock_s3_client
    return service


class TestTavilyCacheService:
    """Tests for TavilyCacheService class."""

    def test_init_default_values(self):
        """Test default configuration values."""
        with patch.dict("os.environ", {}, clear=True):
            service = TavilyCacheService()
            assert service.s3_endpoint == "http://minio:9000"
            assert service.s3_access_key == "minioadmin"
            assert service.s3_secret_key == "minioadmin"
            assert service.bucket == "tavily-cache"
            assert service.scrape_ttl_days == 7
            assert service.search_ttl_days == 1

    def test_init_custom_values(self):
        """Test custom configuration from environment."""
        env = {
            "MINIO_ENDPOINT": "http://custom:9000",
            "MINIO_ACCESS_KEY": "custom_key",
            "MINIO_SECRET_KEY": "custom_secret",
            "TAVILY_CACHE_BUCKET": "custom-bucket",
            "TAVILY_SCRAPE_TTL_DAYS": "14",
            "TAVILY_SEARCH_TTL_DAYS": "3",
        }
        with patch.dict("os.environ", env, clear=True):
            service = TavilyCacheService()
            assert service.s3_endpoint == "http://custom:9000"
            assert service.s3_access_key == "custom_key"
            assert service.s3_secret_key == "custom_secret"
            assert service.bucket == "custom-bucket"
            assert service.scrape_ttl_days == 14
            assert service.search_ttl_days == 3

    def test_hash_key_consistent(self, cache_service):
        """Test that hash key is consistent for same input."""
        url = "https://example.com/page"
        hash1 = cache_service._hash_key(url)
        hash2 = cache_service._hash_key(url)
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_hash_key_different_for_different_inputs(self, cache_service):
        """Test that different inputs produce different hashes."""
        hash1 = cache_service._hash_key("https://example.com/page1")
        hash2 = cache_service._hash_key("https://example.com/page2")
        assert hash1 != hash2

    def test_get_scrape_key_format(self, cache_service):
        """Test scrape key format includes domain and hash."""
        url = "https://example.com/path/to/page"
        key = cache_service._get_scrape_key(url)
        assert key.startswith("scrape/example_com/")
        assert key.endswith(".json")

    def test_get_search_key_format(self, cache_service):
        """Test search key format is normalized."""
        query = "Test Query"
        key = cache_service._get_search_key(query)
        assert key.startswith("search/")
        assert key.endswith(".json")

        # Same query with different case should produce same key
        key_lower = cache_service._get_search_key("test query")
        assert key == key_lower

    def test_is_expired_returns_false_for_fresh_data(self, cache_service):
        """Test that recent data is not expired."""
        recent = datetime.now(timezone.utc).isoformat()
        assert not cache_service._is_expired(recent, ttl_days=7)

    def test_is_expired_returns_true_for_old_data(self, cache_service):
        """Test that old data is expired."""
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        assert cache_service._is_expired(old, ttl_days=7)

    def test_is_expired_returns_true_for_invalid_date(self, cache_service):
        """Test that invalid dates are treated as expired."""
        assert cache_service._is_expired("invalid-date", ttl_days=7)

    def test_get_scraped_content_cache_hit(self, cache_service, mock_s3_client):
        """Test retrieving cached scraped content."""
        cached_data = {
            "url": "https://example.com",
            "content": "Page content",
            "title": "Example Page",
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(cached_data).encode())
        }

        result = cache_service.get_scraped_content("https://example.com")

        assert result is not None
        assert result["content"] == "Page content"
        assert result["title"] == "Example Page"

    def test_get_scraped_content_cache_miss(self, cache_service, mock_s3_client):
        """Test cache miss returns None."""
        from botocore.exceptions import ClientError

        mock_s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )

        result = cache_service.get_scraped_content("https://example.com")
        assert result is None

    def test_get_scraped_content_expired(self, cache_service, mock_s3_client):
        """Test expired cached content returns None."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        cached_data = {
            "url": "https://example.com",
            "content": "Old content",
            "cached_at": old_date,
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(cached_data).encode())
        }

        result = cache_service.get_scraped_content("https://example.com")
        assert result is None

    def test_save_scraped_content(self, cache_service, mock_s3_client):
        """Test saving scraped content to cache."""
        cache_service.save_scraped_content(
            url="https://example.com",
            content="Page content",
            title="Example Page",
            metadata={"extra": "data"},
        )

        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args.kwargs["Bucket"] == "tavily-cache"
        assert call_args.kwargs["ContentType"] == "application/json"

        # Verify saved data structure
        body = json.loads(call_args.kwargs["Body"])
        assert body["url"] == "https://example.com"
        assert body["content"] == "Page content"
        assert body["title"] == "Example Page"
        assert body["metadata"] == {"extra": "data"}
        assert "cached_at" in body

    def test_get_search_results_cache_hit(self, cache_service, mock_s3_client):
        """Test retrieving cached search results."""
        cached_data = {
            "query": "test query",
            "results": [{"title": "Result 1", "url": "https://example.com"}],
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(cached_data).encode())
        }

        result = cache_service.get_search_results("test query")

        assert result is not None
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Result 1"

    def test_get_search_results_expired(self, cache_service, mock_s3_client):
        """Test expired search results returns None."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        cached_data = {
            "query": "test query",
            "results": [],
            "cached_at": old_date,
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(cached_data).encode())
        }

        result = cache_service.get_search_results("test query")
        assert result is None

    def test_save_search_results(self, cache_service, mock_s3_client):
        """Test saving search results to cache."""
        results = [
            {"title": "Result 1", "url": "https://example1.com", "snippet": "Snippet 1"},
            {"title": "Result 2", "url": "https://example2.com", "snippet": "Snippet 2"},
        ]

        cache_service.save_search_results("test query", results, max_results=10)

        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args

        body = json.loads(call_args.kwargs["Body"])
        assert body["query"] == "test query"
        assert body["results"] == results
        assert body["max_results"] == 10
        assert body["result_count"] == 2


class TestGetTavilyCache:
    """Tests for singleton cache getter."""

    def test_returns_singleton(self):
        """Test that get_tavily_cache returns the same instance."""
        # Reset singleton
        import profiler.services.tavily_cache as cache_module
        cache_module._cache_service = None

        cache1 = get_tavily_cache()
        cache2 = get_tavily_cache()

        assert cache1 is cache2

    def test_creates_new_instance_when_none(self):
        """Test that a new instance is created when needed."""
        import profiler.services.tavily_cache as cache_module
        cache_module._cache_service = None

        cache = get_tavily_cache()

        assert cache is not None
        assert isinstance(cache, TavilyCacheService)
