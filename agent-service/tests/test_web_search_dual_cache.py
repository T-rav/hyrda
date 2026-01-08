"""Tests for web search dual cache (Redis + MinIO)."""

from unittest.mock import MagicMock, patch


def test_web_search_caches_to_both_redis_and_minio():
    """Test that web search results are cached to both Redis and MinIO."""
    from agents.system.research.tools.web_search_tool import EnhancedWebSearchTool

    tool = EnhancedWebSearchTool(tavily_api_key="test-key")

    # Mock Redis (ensure get returns None for cache miss)
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    tool.redis_client = mock_redis

    # Mock MinIO file cache
    mock_file_cache = MagicMock()
    mock_file_cache.search_cache.return_value = []  # Cache miss
    tool.file_cache = mock_file_cache

    # Mock Tavily response
    with patch.object(tool, "_search_tavily") as mock_tavily:
        mock_tavily.return_value = ["Result 1", "Result 2"]

        # Execute search
        result = tool._run("test query", "standard")

        # Should return results
        assert "Result 1" in result
        assert "Result 2" in result

        # Should cache to Redis
        mock_redis.setex.assert_called_once()
        redis_call = mock_redis.setex.call_args
        assert "web_search:" in redis_call[0][0]
        assert redis_call[0][1] == 3600  # 1 hour TTL

        # Should cache to MinIO
        mock_file_cache.cache_file.assert_called_once()


def test_web_search_redis_cache_hit():
    """Test that Redis cache is checked first and returns cached results."""
    from agents.system.research.tools.web_search_tool import EnhancedWebSearchTool

    tool = EnhancedWebSearchTool(tavily_api_key="test-key")

    # Mock Redis with cached data
    mock_redis = MagicMock()
    cached_results = "🔍 Web search results for: test\n\n1. Cached Result"
    mock_redis.get.return_value = cached_results
    tool.redis_client = mock_redis

    # Mock file cache (should not be called)
    mock_file_cache = MagicMock()
    tool.file_cache = mock_file_cache

    # Execute search
    result = tool._run("test query", "standard")

    # Should return cached results
    assert "Cached Result" in result
    assert "From cache" in result

    # Should have checked Redis
    mock_redis.get.assert_called_once()

    # Should NOT call Tavily API
    assert "🔍 Web search results" in result or "From cache" in result


def test_web_search_minio_fallback():
    """Test that MinIO is used as fallback when Redis misses."""
    from agents.system.research.tools.web_search_tool import EnhancedWebSearchTool

    tool = EnhancedWebSearchTool(tavily_api_key="test-key")

    # Mock Redis miss
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    tool.redis_client = mock_redis

    # Mock MinIO hit
    mock_file_cache = MagicMock()
    # Use MagicMock instead of CachedFile to avoid validation
    cached_file = MagicMock()
    cached_file.cached_at = "2024-01-01"
    mock_file_cache.search_cache.return_value = [cached_file]
    cached_content = "🔍 Web search results for: test\n\n1. MinIO Cached Result"
    mock_file_cache.retrieve_file.return_value = cached_content
    tool.file_cache = mock_file_cache

    # Execute search
    result = tool._run("test query", "standard")

    # Should return cached results from MinIO
    assert "MinIO Cached Result" in result or "From cache" in result

    # Should have checked Redis first
    mock_redis.get.assert_called_once()

    # Should have checked MinIO
    mock_file_cache.search_cache.assert_called_once()

    # Should re-cache in Redis
    mock_redis.setex.assert_called_once()


def test_web_search_dual_cache_miss():
    """Test that both caches miss triggers fresh API call."""
    from agents.system.research.tools.web_search_tool import EnhancedWebSearchTool

    tool = EnhancedWebSearchTool(tavily_api_key="test-key")

    # Mock Redis miss
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    tool.redis_client = mock_redis

    # Mock MinIO miss
    mock_file_cache = MagicMock()
    mock_file_cache.search_cache.return_value = []
    tool.file_cache = mock_file_cache

    # Mock Tavily API
    with patch.object(tool, "_search_tavily") as mock_tavily:
        mock_tavily.return_value = ["Fresh Result 1", "Fresh Result 2"]

        # Execute search
        result = tool._run("test query", "standard")

        # Should return fresh results
        assert "Fresh Result 1" in result

        # Should have checked both caches
        mock_redis.get.assert_called_once()
        mock_file_cache.search_cache.assert_called_once()

        # Should have called API
        mock_tavily.assert_called_once()

        # Should cache to both
        mock_redis.setex.assert_called_once()
        mock_file_cache.cache_file.assert_called_once()


def test_web_search_deep_search_bypasses_cache():
    """Test that deep search always fetches fresh data."""
    from agents.system.research.tools.web_search_tool import EnhancedWebSearchTool

    tool = EnhancedWebSearchTool(tavily_api_key="test-key")

    # Mock Redis (should not be checked)
    mock_redis = MagicMock()
    tool.redis_client = mock_redis

    # Mock Tavily API
    with patch.object(tool, "_search_tavily") as mock_tavily:
        mock_tavily.return_value = ["Deep Result 1"]

        # Execute deep search
        tool._run("test query", "deep")

        # Should call API directly (no cache check)
        mock_tavily.assert_called_once()

        # Should not check cache for deep search
        mock_redis.get.assert_not_called()

        # Should still cache results
        mock_redis.setex.assert_called_once()


def test_web_search_cache_key_generation():
    """Test that cache keys are generated consistently."""
    from agents.system.research.tools.web_search_tool import EnhancedWebSearchTool

    tool = EnhancedWebSearchTool()

    # Same query should generate same key
    key1 = tool._get_cache_key("test query", "standard")
    key2 = tool._get_cache_key("test query", "standard")
    assert key1 == key2

    # Different query should generate different key
    key3 = tool._get_cache_key("different query", "standard")
    assert key1 != key3

    # Different depth should generate different key
    key4 = tool._get_cache_key("test query", "deep")
    assert key1 != key4

    # Key should be prefixed
    assert key1.startswith("web_search:")


def test_web_search_graceful_degradation():
    """Test that search works with only one cache layer available."""
    from agents.system.research.tools.web_search_tool import EnhancedWebSearchTool

    # Only Redis available
    tool = EnhancedWebSearchTool(tavily_api_key="test-key")
    mock_redis = MagicMock()
    mock_redis.get.return_value = None  # Cache miss
    tool.redis_client = mock_redis
    tool.file_cache = None

    with patch.object(tool, "_search_tavily") as mock_tavily:
        mock_tavily.return_value = ["Result 1"]

        result = tool._run("test query", "standard")

        # Should still work and cache to Redis
        assert "Result 1" in result
        mock_redis.setex.assert_called_once()

    # Only MinIO available
    tool2 = EnhancedWebSearchTool(tavily_api_key="test-key")
    tool2.redis_client = None
    mock_file_cache = MagicMock()
    tool2.file_cache = mock_file_cache

    with patch.object(tool2, "_search_tavily") as mock_tavily:
        mock_tavily.return_value = ["Result 2"]

        result = tool2._run("test query", "standard")

        # Should still work and cache to MinIO
        assert "Result 2" in result
        mock_file_cache.cache_file.assert_called_once()


def test_web_search_handles_cache_errors_gracefully():
    """Test that cache errors don't break search functionality."""
    from agents.system.research.tools.web_search_tool import EnhancedWebSearchTool

    tool = EnhancedWebSearchTool(tavily_api_key="test-key")

    # Mock Redis that raises errors
    mock_redis = MagicMock()
    mock_redis.get.side_effect = Exception("Redis connection failed")
    mock_redis.setex.side_effect = Exception("Redis connection failed")
    tool.redis_client = mock_redis

    # Mock file cache that raises errors
    mock_file_cache = MagicMock()
    mock_file_cache.search_cache.side_effect = Exception("MinIO connection failed")
    tool.file_cache = mock_file_cache

    # Should still work by calling API
    with patch.object(tool, "_search_tavily") as mock_tavily:
        mock_tavily.return_value = ["Result 1"]

        result = tool._run("test query", "standard")

        # Should return results despite cache errors
        assert "Result 1" in result
        mock_tavily.assert_called_once()
