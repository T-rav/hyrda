"""Redis cache for SEC filings to avoid re-fetching and re-embedding.

Caches both raw filing data and pre-computed embeddings for 1 hour.
"""

import base64
import json
import logging
from datetime import UTC, datetime
from typing import Any

import numpy as np
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SECFilingsCache:
    """Redis-based cache for SEC filings and embeddings."""

    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 3600):
        """Initialize SEC filings cache.

        Args:
            redis_url: Redis connection URL
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        self.redis_url = redis_url
        self.ttl = ttl  # 1 hour default
        self.redis_client = None
        self._redis_available = None

    async def _get_redis_client(self) -> redis.Redis | None:
        """Get Redis client with connection health check."""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=False,  # Keep binary for numpy arrays
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                # Test connection
                await self.redis_client.ping()
                self._redis_available = True
                logger.info(f"SEC cache connected to Redis at {self.redis_url}")
            except Exception as e:
                logger.warning(
                    f"SEC cache: Redis connection failed: {e}. Caching disabled."
                )
                self._redis_available = False
                self.redis_client = None

        return self.redis_client if self._redis_available else None

    def _get_cache_key(self, company_identifier: str) -> str:
        """Generate cache key for company SEC filings.

        Uses current date to ensure daily refresh (SEC updates once per day max).

        Args:
            company_identifier: Ticker or CIK

        Returns:
            Cache key string
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return f"sec_filings:{company_identifier.upper()}:{today}"

    def _serialize_embeddings(self, embeddings: np.ndarray) -> str:
        """Serialize numpy embeddings array to base64 string.

        Args:
            embeddings: Numpy array of embeddings

        Returns:
            Base64-encoded string
        """
        return base64.b64encode(embeddings.tobytes()).decode("utf-8")

    def _deserialize_embeddings(
        self, encoded: str, shape: tuple[int, ...], dtype: str
    ) -> np.ndarray:
        """Deserialize base64 string back to numpy array.

        Args:
            encoded: Base64-encoded embeddings
            shape: Original array shape
            dtype: Original array dtype

        Returns:
            Numpy array
        """
        decoded = base64.b64decode(encoded)
        return np.frombuffer(decoded, dtype=dtype).reshape(shape)

    async def get_cached_filings(
        self, company_identifier: str
    ) -> dict[str, Any] | None:
        """Get cached SEC filings and embeddings.

        Args:
            company_identifier: Ticker or CIK

        Returns:
            Cached data dict or None if not found
        """
        redis_client = await self._get_redis_client()
        if not redis_client:
            return None

        cache_key = self._get_cache_key(company_identifier)

        try:
            cached_bytes = await redis_client.get(cache_key)
            if not cached_bytes:
                logger.debug(f"SEC cache miss for {company_identifier}")
                return None

            # Deserialize JSON
            cached_str = cached_bytes.decode("utf-8")
            cached_data = json.loads(cached_str)

            # Deserialize embeddings if present
            if "embeddings" in cached_data:
                embeddings_data = cached_data["embeddings"]
                cached_data["embeddings"] = self._deserialize_embeddings(
                    embeddings_data["data"],
                    tuple(embeddings_data["shape"]),
                    embeddings_data["dtype"],
                )

            logger.info(
                f"SEC cache hit for {company_identifier} "
                f"({cached_data.get('total_chunks', 0)} chunks)"
            )
            return cached_data

        except Exception as e:
            logger.warning(f"SEC cache retrieval failed for {company_identifier}: {e}")
            return None

    async def cache_filings(
        self,
        company_identifier: str,
        company_name: str,
        filings: list[dict[str, Any]],
        chunks: list[str],
        chunk_metadata: list[dict[str, Any]],
        embeddings: np.ndarray | None = None,
    ) -> bool:
        """Cache SEC filings data and embeddings.

        Args:
            company_identifier: Ticker or CIK
            company_name: Full company name
            filings: List of filing metadata
            chunks: List of text chunks
            chunk_metadata: List of metadata dicts for each chunk
            embeddings: Optional pre-computed embeddings array

        Returns:
            True if cached successfully, False otherwise
        """
        redis_client = await self._get_redis_client()
        if not redis_client:
            return False

        cache_key = self._get_cache_key(company_identifier)

        try:
            # Prepare data for caching
            cache_data = {
                "company_name": company_name,
                "company_identifier": company_identifier,
                "filings": filings,
                "chunks": chunks,
                "chunk_metadata": chunk_metadata,
                "total_chunks": len(chunks),
                "total_characters": sum(len(chunk) for chunk in chunks),
                "cached_at": datetime.now(UTC).isoformat(),
            }

            # Serialize embeddings if provided
            if embeddings is not None:
                cache_data["embeddings"] = {
                    "data": self._serialize_embeddings(embeddings),
                    "shape": embeddings.shape,
                    "dtype": str(embeddings.dtype),
                }

            # Serialize to JSON and store
            cache_bytes = json.dumps(cache_data).encode("utf-8")
            await redis_client.setex(cache_key, self.ttl, cache_bytes)

            logger.info(
                f"Cached SEC filings for {company_identifier} "
                f"({len(chunks)} chunks, {len(cache_bytes):,} bytes, TTL={self.ttl}s)"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to cache SEC filings for {company_identifier}: {e}")
            return False

    async def clear_cache(self, company_identifier: str | None = None) -> bool:
        """Clear cached SEC filings.

        Args:
            company_identifier: Optional specific company to clear (clears all if None)

        Returns:
            True if cleared successfully
        """
        redis_client = await self._get_redis_client()
        if not redis_client:
            return False

        try:
            if company_identifier:
                # Clear specific company
                cache_key = self._get_cache_key(company_identifier)
                await redis_client.delete(cache_key)
                logger.info(f"Cleared SEC cache for {company_identifier}")
            else:
                # Clear all SEC caches
                pattern = "sec_filings:*"
                keys = []
                async for key in redis_client.scan_iter(match=pattern):
                    keys.append(key)

                if keys:
                    await redis_client.delete(*keys)
                    logger.info(f"Cleared {len(keys)} SEC cache entries")

            return True

        except Exception as e:
            logger.warning(f"Failed to clear SEC cache: {e}")
            return False
