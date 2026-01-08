"""Thread-to-agent tracking service with Redis persistence.

Tracks which agent (e.g., meddic, profile) started a thread to enable
continuous conversation without repeating command prefixes.
"""

import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class ThreadTrackingService:
    """Redis-backed thread-to-agent tracking with in-memory fallback."""

    # Thread tracking TTL: 24 hours (conversations don't last forever)
    THREAD_TTL = 86400

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize thread tracking service.

        Args:
            redis_url: Redis connection URL

        """
        self.redis_url = redis_url
        self.redis_client = None
        self._redis_available = None
        # In-memory fallback
        self._memory_map: dict[str, str] = {}

    async def _get_redis_client(self) -> redis.Redis | None:
        """Get Redis client with connection health check."""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                # Test connection
                await self.redis_client.ping()
                self._redis_available = True
                logger.info(f"Thread tracking using Redis at {self.redis_url}")
            except Exception as e:
                logger.warning(
                    f"Redis unavailable for thread tracking: {e}. Using in-memory fallback."
                )
                self._redis_available = False
                self.redis_client = None

        return self.redis_client if self._redis_available else None

    def _get_cache_key(self, thread_ts: str) -> str:
        """Generate Redis key for thread tracking."""
        return f"thread_agent:{thread_ts}"

    async def track_thread(self, thread_ts: str, agent_name: str) -> bool:
        """Track that a thread belongs to an agent.

        Args:
            thread_ts: Thread timestamp
            agent_name: Agent name (e.g., "meddic", "profile")

        Returns:
            True if successfully tracked

        """
        redis_client = await self._get_redis_client()

        # Try Redis first
        if redis_client:
            try:
                cache_key = self._get_cache_key(thread_ts)
                await redis_client.setex(cache_key, self.THREAD_TTL, agent_name)
                logger.info(
                    f"📌 Tracked thread {thread_ts} → {agent_name} (Redis, TTL={self.THREAD_TTL}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Redis tracking failed: {e}, falling back to memory")

        # Fallback to memory
        self._memory_map[thread_ts] = agent_name
        logger.info(f"📌 Tracked thread {thread_ts} → {agent_name} (memory)")
        return True

    async def get_thread_agent(self, thread_ts: str) -> str | None:
        """Get which agent owns a thread.

        Args:
            thread_ts: Thread timestamp

        Returns:
            Agent name if tracked, None otherwise

        """
        redis_client = await self._get_redis_client()

        # Try Redis first
        if redis_client:
            try:
                cache_key = self._get_cache_key(thread_ts)
                agent_name = await redis_client.get(cache_key)
                if agent_name:
                    logger.debug(f"🔗 Thread {thread_ts} → {agent_name} (Redis)")
                    return agent_name
            except Exception as e:
                logger.warning(f"Redis lookup failed: {e}, checking memory")

        # Fallback to memory
        agent_name = self._memory_map.get(thread_ts)
        if agent_name:
            logger.debug(f"🔗 Thread {thread_ts} → {agent_name} (memory)")
        return agent_name

    async def clear_thread(self, thread_ts: str) -> bool:
        """Clear thread tracking.

        Args:
            thread_ts: Thread timestamp

        Returns:
            True if thread was tracked and cleared

        """
        redis_client = await self._get_redis_client()
        cleared = False

        # Try Redis first
        if redis_client:
            try:
                cache_key = self._get_cache_key(thread_ts)
                result = await redis_client.delete(cache_key)
                if result > 0:
                    logger.info(f"🔓 Cleared thread {thread_ts} (Redis)")
                    cleared = True
            except Exception as e:
                logger.warning(f"Redis clear failed: {e}, checking memory")

        # Also check/clear memory
        if thread_ts in self._memory_map:
            del self._memory_map[thread_ts]
            logger.info(f"🔓 Cleared thread {thread_ts} (memory)")
            cleared = True

        return cleared

    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Thread tracking Redis connection closed")


# Global instance
_thread_tracking: ThreadTrackingService | None = None


def get_thread_tracking(redis_url: str | None = None) -> ThreadTrackingService:
    """Get or create the global thread tracking service.

    Args:
        redis_url: Optional Redis URL (only used on first init)

    Returns:
        ThreadTrackingService instance

    """
    global _thread_tracking  # noqa: PLW0603
    if _thread_tracking is None:
        # Get Redis URL from settings if not provided
        if redis_url is None:
            try:
                from config.settings import CacheSettings

                cache_settings = CacheSettings()
                redis_url = cache_settings.redis_url
                logger.info(f"Thread tracking initialized with Redis: {redis_url}")
            except Exception as e:
                logger.warning(f"Could not get Redis URL from settings: {e}")
                redis_url = "redis://localhost:6379"

        _thread_tracking = ThreadTrackingService(redis_url=redis_url)
    return _thread_tracking
