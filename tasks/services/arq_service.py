"""ARQ (Async Redis Queue) service for distributed job execution across workers."""

import logging
import os
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

logger = logging.getLogger(__name__)


class ARQService:
    """Service for managing ARQ queues and workers."""

    def __init__(self, redis_url: str | None = None):
        """
        Initialize ARQ service.

        Args:
            redis_url: Redis connection URL (defaults to CACHE_REDIS_URL env var)
        """
        self.redis_url = redis_url or os.getenv("CACHE_REDIS_URL", "redis://redis:6379")
        self.redis_pool: ArqRedis | None = None

        # Parse Redis URL for ARQ
        # Format: redis://host:port or redis://host:port/db
        url_parts = self.redis_url.replace("redis://", "").split(":")
        host = url_parts[0]
        port_and_db = url_parts[1] if len(url_parts) > 1 else "6379"
        port = int(port_and_db.split("/")[0])
        db = int(port_and_db.split("/")[1]) if "/" in port_and_db else 0

        self.redis_settings = RedisSettings(host=host, port=port, database=db)

    async def initialize(self) -> None:
        """Initialize Redis connection pool."""
        try:
            # Create ARQ Redis pool
            self.redis_pool = await create_pool(self.redis_settings)

            logger.info(f"✅ ARQ service initialized (redis: {self.redis_url})")

        except Exception as e:
            logger.error(f"Failed to initialize ARQ service: {e}")
            raise

    async def enqueue_job(
        self,
        func_name: str,
        *args: Any,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Enqueue a job to ARQ for distributed execution.

        Args:
            func_name: Function name to execute (e.g., "execute_job_by_type")
            *args: Positional arguments for the function
            job_id: Optional job ID (for deduplication and tracking)
            **kwargs: Keyword arguments for the function

        Returns:
            ARQ job ID

        Raises:
            RuntimeError: If pool not initialized
        """
        if not self.redis_pool:
            raise RuntimeError("ARQ service not initialized - call initialize() first")

        try:
            # Enqueue job to ARQ
            # ARQ expects function to be in the worker's function registry
            job = await self.redis_pool.enqueue_job(
                func_name,
                *args,
                _job_id=job_id,
                _timeout=3600,  # 1 hour timeout for long-running jobs
                **kwargs,
            )

            logger.debug(f"Enqueued job {job.job_id} to ARQ: {func_name}")
            return job.job_id

        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown Redis connection pool."""
        if self.redis_pool:
            await self.redis_pool.close()
            logger.info("ARQ service shut down")


# Global ARQ service instance (initialized in app.py lifespan)
_arq_service: ARQService | None = None


def get_arq_service() -> ARQService:
    """Get the global ARQ service instance."""
    if _arq_service is None:
        raise RuntimeError("ARQ service not initialized")
    return _arq_service


def set_arq_service(service: ARQService) -> None:
    """Set the global ARQ service instance."""
    global _arq_service
    _arq_service = service
