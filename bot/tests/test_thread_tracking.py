"""
Tests for ThreadTrackingService.

Tests the thread-to-agent tracking service including:
- Redis connection management with fallback
- Thread tracking with TTL
- Thread retrieval from Redis and memory
- Thread clearing
- Connection health checks
- In-memory fallback behavior
- Global instance management
"""

from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis

from services.thread_tracking import (
    ThreadTrackingService,
    get_thread_tracking,
)


# TDD Factory Patterns for ThreadTracking Testing
class RedisClientFactory:
    """Factory for creating mock Redis clients"""

    @staticmethod
    def create_healthy_redis_client() -> AsyncMock:
        """Create a healthy Redis client mock"""
        mock_client = AsyncMock(spec=redis.Redis)
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.setex = AsyncMock(return_value=True)
        mock_client.get = AsyncMock(return_value=None)
        mock_client.delete = AsyncMock(return_value=0)
        mock_client.close = AsyncMock()
        return mock_client

    @staticmethod
    def create_failing_redis_client() -> AsyncMock:
        """Create a Redis client that fails on ping"""
        mock_client = AsyncMock(spec=redis.Redis)
        mock_client.ping = AsyncMock(
            side_effect=redis.ConnectionError("Connection failed")
        )
        return mock_client

    @staticmethod
    def create_redis_with_tracked_thread(thread_ts: str, agent_name: str) -> AsyncMock:
        """Create Redis client with an existing tracked thread"""
        mock_client = AsyncMock(spec=redis.Redis)
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.get = AsyncMock(return_value=agent_name)
        mock_client.setex = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.close = AsyncMock()
        return mock_client

    @staticmethod
    def create_redis_with_transient_failures() -> AsyncMock:
        """Create Redis client that fails intermittently"""
        mock_client = AsyncMock(spec=redis.Redis)
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.setex = AsyncMock(
            side_effect=redis.TimeoutError("Operation timed out")
        )
        mock_client.get = AsyncMock(
            side_effect=redis.TimeoutError("Operation timed out")
        )
        mock_client.delete = AsyncMock(
            side_effect=redis.TimeoutError("Operation timed out")
        )
        mock_client.close = AsyncMock()
        return mock_client


class ThreadTrackingTestDataFactory:
    """Factory for creating test data"""

    @staticmethod
    def create_thread_ts() -> str:
        """Create test thread timestamp"""
        return "1234567890.123456"

    @staticmethod
    def create_agent_name() -> str:
        """Create test agent name"""
        return "meddic"

    @staticmethod
    def create_another_agent_name() -> str:
        """Create another test agent name"""
        return "profile"

    @staticmethod
    def create_redis_url() -> str:
        """Create test Redis URL"""
        return "redis://localhost:6379"

    @staticmethod
    def create_cache_key(thread_ts: str) -> str:
        """Create expected cache key"""
        return f"thread_agent:{thread_ts}"


# Fixtures
@pytest.fixture
def thread_ts() -> str:
    """Provide test thread timestamp"""
    return ThreadTrackingTestDataFactory.create_thread_ts()


@pytest.fixture
def agent_name() -> str:
    """Provide test agent name"""
    return ThreadTrackingTestDataFactory.create_agent_name()


@pytest.fixture
def redis_url() -> str:
    """Provide test Redis URL"""
    return ThreadTrackingTestDataFactory.create_redis_url()


@pytest.fixture
def service(redis_url: str) -> ThreadTrackingService:
    """Create ThreadTrackingService instance"""
    return ThreadTrackingService(redis_url=redis_url)


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Provide healthy mock Redis client"""
    return RedisClientFactory.create_healthy_redis_client()


# Test Suite


class TestThreadTrackingServiceInitialization:
    """Test service initialization"""

    def test_init_creates_service_with_redis_url(self, redis_url: str):
        """Test that service initializes with Redis URL"""
        # Arrange & Act
        service = ThreadTrackingService(redis_url=redis_url)

        # Assert
        assert service.redis_url == redis_url
        assert service.redis_client is None
        assert service._redis_available is None
        assert service._memory_map == {}

    def test_init_creates_service_with_default_url(self):
        """Test that service initializes with default Redis URL"""
        # Arrange & Act
        service = ThreadTrackingService()

        # Assert
        assert service.redis_url == "redis://localhost:6379"
        assert service._memory_map == {}


class TestRedisClientManagement:
    """Test Redis client creation and health checks"""

    @pytest.mark.asyncio
    async def test_get_redis_client_creates_connection_on_first_call(
        self, service: ThreadTrackingService
    ):
        """Test that Redis client is created on first call"""
        # Arrange
        mock_client = RedisClientFactory.create_healthy_redis_client()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            client = await service._get_redis_client()

            # Assert
            assert client is mock_client
            assert service.redis_client is mock_client
            assert service._redis_available is True
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_redis_client_reuses_existing_connection(
        self, service: ThreadTrackingService
    ):
        """Test that Redis client is reused after first call"""
        # Arrange
        mock_client = RedisClientFactory.create_healthy_redis_client()
        service.redis_client = mock_client
        service._redis_available = True

        # Act
        client = await service._get_redis_client()

        # Assert
        assert client is mock_client
        # ping should not be called again
        mock_client.ping.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_redis_client_handles_connection_failure(
        self, service: ThreadTrackingService
    ):
        """Test that service falls back to memory when Redis unavailable"""
        # Arrange
        mock_client = RedisClientFactory.create_failing_redis_client()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            client = await service._get_redis_client()

            # Assert
            assert client is None
            assert service._redis_available is False
            assert service.redis_client is None

    @pytest.mark.asyncio
    async def test_get_redis_client_returns_none_after_failed_connection(
        self, redis_url: str
    ):
        """Test that subsequent calls return None after connection failure"""
        # Arrange
        service = ThreadTrackingService(redis_url=redis_url)
        # Simulate a Redis client that was set but marked unavailable
        mock_client = RedisClientFactory.create_healthy_redis_client()
        service.redis_client = mock_client
        service._redis_available = False

        # Act
        client = await service._get_redis_client()

        # Assert
        assert client is None


class TestCacheKeyGeneration:
    """Test Redis key generation"""

    def test_get_cache_key_generates_correct_format(
        self, service: ThreadTrackingService, thread_ts: str
    ):
        """Test that cache key is generated correctly"""
        # Arrange
        expected_key = ThreadTrackingTestDataFactory.create_cache_key(thread_ts)

        # Act
        cache_key = service._get_cache_key(thread_ts)

        # Assert
        assert cache_key == expected_key
        assert cache_key.startswith("thread_agent:")


class TestThreadTracking:
    """Test tracking threads to agents"""

    @pytest.mark.asyncio
    async def test_track_thread_stores_in_redis_when_available(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that thread tracking uses Redis when available"""
        # Arrange
        mock_client = RedisClientFactory.create_healthy_redis_client()
        expected_key = ThreadTrackingTestDataFactory.create_cache_key(thread_ts)

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.track_thread(thread_ts, agent_name)

            # Assert
            assert result is True
            mock_client.setex.assert_called_once_with(
                expected_key, ThreadTrackingService.THREAD_TTL, agent_name
            )
            # Should not be in memory map when Redis succeeds
            assert thread_ts not in service._memory_map

    @pytest.mark.asyncio
    async def test_track_thread_falls_back_to_memory_when_redis_unavailable(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that thread tracking falls back to memory when Redis unavailable"""
        # Arrange
        mock_client = RedisClientFactory.create_failing_redis_client()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.track_thread(thread_ts, agent_name)

            # Assert
            assert result is True
            assert service._memory_map[thread_ts] == agent_name

    @pytest.mark.asyncio
    async def test_track_thread_falls_back_to_memory_on_redis_error(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that thread tracking falls back to memory on Redis operation error"""
        # Arrange
        mock_client = RedisClientFactory.create_redis_with_transient_failures()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.track_thread(thread_ts, agent_name)

            # Assert
            assert result is True
            assert service._memory_map[thread_ts] == agent_name

    @pytest.mark.asyncio
    async def test_track_thread_updates_existing_tracking(
        self, service: ThreadTrackingService, thread_ts: str
    ):
        """Test that tracking can be updated for the same thread"""
        # Arrange
        first_agent = ThreadTrackingTestDataFactory.create_agent_name()
        second_agent = ThreadTrackingTestDataFactory.create_another_agent_name()
        mock_client = RedisClientFactory.create_healthy_redis_client()
        expected_key = ThreadTrackingTestDataFactory.create_cache_key(thread_ts)

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            await service.track_thread(thread_ts, first_agent)
            await service.track_thread(thread_ts, second_agent)

            # Assert
            assert mock_client.setex.call_count == 2
            # Verify last call used second agent
            mock_client.setex.assert_called_with(
                expected_key, ThreadTrackingService.THREAD_TTL, second_agent
            )

    @pytest.mark.asyncio
    async def test_track_thread_respects_ttl(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that tracked threads have correct TTL"""
        # Arrange
        mock_client = RedisClientFactory.create_healthy_redis_client()
        expected_ttl = ThreadTrackingService.THREAD_TTL

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            await service.track_thread(thread_ts, agent_name)

            # Assert
            call_args = mock_client.setex.call_args
            assert call_args[0][1] == expected_ttl  # TTL argument


class TestThreadRetrieval:
    """Test retrieving tracked threads"""

    @pytest.mark.asyncio
    async def test_get_thread_agent_returns_from_redis_when_available(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that thread agent is retrieved from Redis"""
        # Arrange
        mock_client = RedisClientFactory.create_redis_with_tracked_thread(
            thread_ts, agent_name
        )
        expected_key = ThreadTrackingTestDataFactory.create_cache_key(thread_ts)

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.get_thread_agent(thread_ts)

            # Assert
            assert result == agent_name
            mock_client.get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_get_thread_agent_returns_none_when_not_tracked(
        self, service: ThreadTrackingService, thread_ts: str
    ):
        """Test that None is returned for untracked threads"""
        # Arrange
        mock_client = RedisClientFactory.create_healthy_redis_client()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.get_thread_agent(thread_ts)

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_get_thread_agent_falls_back_to_memory_when_redis_unavailable(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that thread retrieval falls back to memory"""
        # Arrange
        mock_client = RedisClientFactory.create_failing_redis_client()
        service._memory_map[thread_ts] = agent_name

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.get_thread_agent(thread_ts)

            # Assert
            assert result == agent_name

    @pytest.mark.asyncio
    async def test_get_thread_agent_falls_back_to_memory_on_redis_error(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that thread retrieval falls back to memory on Redis error"""
        # Arrange
        mock_client = RedisClientFactory.create_redis_with_transient_failures()
        service._memory_map[thread_ts] = agent_name

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.get_thread_agent(thread_ts)

            # Assert
            assert result == agent_name

    @pytest.mark.asyncio
    async def test_get_thread_agent_returns_none_from_memory_when_not_found(
        self, service: ThreadTrackingService, thread_ts: str
    ):
        """Test that None is returned when thread not in memory"""
        # Arrange
        mock_client = RedisClientFactory.create_failing_redis_client()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.get_thread_agent(thread_ts)

            # Assert
            assert result is None
            assert thread_ts not in service._memory_map


class TestThreadClearing:
    """Test clearing thread tracking"""

    @pytest.mark.asyncio
    async def test_clear_thread_removes_from_redis(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that thread is cleared from Redis"""
        # Arrange
        mock_client = RedisClientFactory.create_redis_with_tracked_thread(
            thread_ts, agent_name
        )
        expected_key = ThreadTrackingTestDataFactory.create_cache_key(thread_ts)

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.clear_thread(thread_ts)

            # Assert
            assert result is True
            mock_client.delete.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_clear_thread_returns_false_when_not_tracked(
        self, service: ThreadTrackingService, thread_ts: str
    ):
        """Test that clear returns False for untracked threads"""
        # Arrange
        mock_client = RedisClientFactory.create_healthy_redis_client()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.clear_thread(thread_ts)

            # Assert
            assert result is False

    @pytest.mark.asyncio
    async def test_clear_thread_removes_from_memory(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that thread is cleared from memory"""
        # Arrange
        mock_client = RedisClientFactory.create_failing_redis_client()
        service._memory_map[thread_ts] = agent_name

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.clear_thread(thread_ts)

            # Assert
            assert result is True
            assert thread_ts not in service._memory_map

    @pytest.mark.asyncio
    async def test_clear_thread_handles_redis_error_gracefully(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that clear handles Redis errors and still checks memory"""
        # Arrange
        mock_client = RedisClientFactory.create_redis_with_transient_failures()
        service._memory_map[thread_ts] = agent_name

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.clear_thread(thread_ts)

            # Assert
            assert result is True
            assert thread_ts not in service._memory_map

    @pytest.mark.asyncio
    async def test_clear_thread_clears_both_redis_and_memory(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test that clear removes from both Redis and memory"""
        # Arrange
        mock_client = RedisClientFactory.create_redis_with_tracked_thread(
            thread_ts, agent_name
        )
        service._memory_map[thread_ts] = agent_name

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            result = await service.clear_thread(thread_ts)

            # Assert
            assert result is True
            mock_client.delete.assert_called_once()
            assert thread_ts not in service._memory_map


class TestConnectionClose:
    """Test closing Redis connections"""

    @pytest.mark.asyncio
    async def test_close_closes_redis_connection(self, service: ThreadTrackingService):
        """Test that close properly closes Redis connection"""
        # Arrange
        mock_client = RedisClientFactory.create_healthy_redis_client()
        service.redis_client = mock_client

        # Act
        await service.close()

        # Assert
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_no_connection_gracefully(
        self, service: ThreadTrackingService
    ):
        """Test that close handles no connection gracefully"""
        # Arrange
        service.redis_client = None

        # Act & Assert (should not raise)
        await service.close()


class TestGlobalInstanceManagement:
    """Test global instance getter"""

    def test_get_thread_tracking_creates_instance_on_first_call(self):
        """Test that get_thread_tracking creates instance on first call"""
        # Arrange - reset global
        import services.thread_tracking

        services.thread_tracking._thread_tracking = None

        # Act
        with patch("config.settings.CacheSettings") as mock_cache_settings:
            mock_cache_settings.return_value.redis_url = "redis://test:6379"
            service = get_thread_tracking()

            # Assert
            assert service is not None
            assert isinstance(service, ThreadTrackingService)

    def test_get_thread_tracking_reuses_existing_instance(self):
        """Test that get_thread_tracking reuses existing instance"""
        # Arrange
        import services.thread_tracking

        services.thread_tracking._thread_tracking = None

        with patch("config.settings.CacheSettings") as mock_cache_settings:
            mock_cache_settings.return_value.redis_url = "redis://test:6379"

            # Act
            service1 = get_thread_tracking()
            service2 = get_thread_tracking()

            # Assert
            assert service1 is service2

    def test_get_thread_tracking_uses_provided_redis_url(self):
        """Test that get_thread_tracking uses provided Redis URL"""
        # Arrange
        import services.thread_tracking

        services.thread_tracking._thread_tracking = None
        custom_url = "redis://custom:6379"

        # Act
        service = get_thread_tracking(redis_url=custom_url)

        # Assert
        assert service.redis_url == custom_url

    def test_get_thread_tracking_handles_settings_error(self):
        """Test that get_thread_tracking handles settings errors gracefully"""
        # Arrange
        import services.thread_tracking

        services.thread_tracking._thread_tracking = None

        with patch(
            "config.settings.CacheSettings",
            side_effect=Exception("Settings error"),
        ):
            # Act
            service = get_thread_tracking()

            # Assert
            assert service is not None
            assert service.redis_url == "redis://localhost:6379"


class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    @pytest.mark.asyncio
    async def test_track_retrieve_clear_workflow_with_redis(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test complete workflow: track → retrieve → clear with Redis"""
        # Arrange
        mock_client = RedisClientFactory.create_redis_with_tracked_thread(
            thread_ts, agent_name
        )

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act & Assert - Track
            track_result = await service.track_thread(thread_ts, agent_name)
            assert track_result is True

            # Act & Assert - Retrieve
            retrieved_agent = await service.get_thread_agent(thread_ts)
            assert retrieved_agent == agent_name

            # Act & Assert - Clear
            clear_result = await service.clear_thread(thread_ts)
            assert clear_result is True

            # Act & Assert - Retrieve after clear (should be None)
            mock_client.get = AsyncMock(return_value=None)
            retrieved_after_clear = await service.get_thread_agent(thread_ts)
            assert retrieved_after_clear is None

    @pytest.mark.asyncio
    async def test_track_retrieve_clear_workflow_with_memory(
        self, service: ThreadTrackingService, thread_ts: str, agent_name: str
    ):
        """Test complete workflow: track → retrieve → clear with memory"""
        # Arrange
        mock_client = RedisClientFactory.create_failing_redis_client()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act & Assert - Track
            track_result = await service.track_thread(thread_ts, agent_name)
            assert track_result is True

            # Act & Assert - Retrieve
            retrieved_agent = await service.get_thread_agent(thread_ts)
            assert retrieved_agent == agent_name

            # Act & Assert - Clear
            clear_result = await service.clear_thread(thread_ts)
            assert clear_result is True

            # Act & Assert - Retrieve after clear (should be None)
            retrieved_after_clear = await service.get_thread_agent(thread_ts)
            assert retrieved_after_clear is None

    @pytest.mark.asyncio
    async def test_multiple_threads_tracked_independently(
        self, service: ThreadTrackingService
    ):
        """Test that multiple threads can be tracked independently"""
        # Arrange
        thread1 = "1111111111.111111"
        thread2 = "2222222222.222222"
        agent1 = "meddic"
        agent2 = "profile"
        mock_client = RedisClientFactory.create_healthy_redis_client()

        def mock_get(key):
            if key == f"thread_agent:{thread1}":
                return agent1
            elif key == f"thread_agent:{thread2}":
                return agent2
            return None

        mock_client.get = AsyncMock(side_effect=mock_get)

        with patch("redis.asyncio.from_url", return_value=mock_client):
            # Act
            await service.track_thread(thread1, agent1)
            await service.track_thread(thread2, agent2)

            # Assert
            retrieved1 = await service.get_thread_agent(thread1)
            retrieved2 = await service.get_thread_agent(thread2)

            assert retrieved1 == agent1
            assert retrieved2 == agent2
            assert mock_client.setex.call_count == 2
