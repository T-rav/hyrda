"""RQ (Redis Queue) service for distributed job execution across workers."""

import logging
import os
from typing import Any

from aiorq import Queue
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RQService:
    """Service for managing RQ queues and workers."""

    def __init__(self, redis_url: str | None = None):
        """
        Initialize RQ service.

        Args:
            redis_url: Redis connection URL (defaults to CACHE_REDIS_URL env var)
        """
        self.redis_url = redis_url or os.getenv("CACHE_REDIS_URL", "redis://redis:6379")
        self.redis_client: Redis | None = None
        self.queue: Queue | None = None

    async def initialize(self) -> None:
        """Initialize Redis connection and queue."""
        try:
            # Create async Redis client
            self.redis_client = Redis.from_url(
                self.redis_url,
                decode_responses=False,  # RQ requires bytes
                max_connections=20,
            )

            # Create default queue for job execution
            self.queue = Queue(name="default", connection=self.redis_client)

            logger.info(
                f"✅ RQ service initialized (queue: default, redis: {self.redis_url})"
            )

        except Exception as e:
            logger.error(f"Failed to initialize RQ service: {e}")
            raise

    async def enqueue_job(
        self,
        func_name: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> str:
        """
        Enqueue a job to RQ for distributed execution.

        Args:
            func_name: Fully qualified function name (e.g., "jobs.job_registry.execute_job_by_type")
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            job_id: Optional job ID (for deduplication and tracking)

        Returns:
            RQ job ID

        Raises:
            RuntimeError: If queue not initialized
        """
        if not self.queue:
            raise RuntimeError("RQ service not initialized - call initialize() first")

        try:
            # Enqueue job to RQ
            job = await self.queue.enqueue(
                func_name,
                *args or [],
                **kwargs or {},
                job_id=job_id,
                timeout=3600,  # 1 hour timeout for long-running jobs
            )

            logger.debug(f"Enqueued job {job.id} to RQ queue: {func_name}")
            return job.id

        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("RQ service shut down")


# Global RQ service instance (initialized in app.py lifespan)
_rq_service: RQService | None = None


def get_rq_service() -> RQService:
    """Get the global RQ service instance."""
    if _rq_service is None:
        raise RuntimeError("RQ service not initialized")
    return _rq_service


def set_rq_service(service: RQService) -> None:
    """Set the global RQ service instance."""
    global _rq_service
    _rq_service = service
