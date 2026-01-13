"""Dual cache for SEC filings (Redis + MinIO) to avoid re-fetching and re-embedding.

Caches both raw filing data and pre-computed embeddings:
- Redis: Fast access (1 hour TTL)
- MinIO: Long-term storage (30 days)
"""

import base64
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3
import numpy as np
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SECFilingsCache:
    """Dual cache (Redis + MinIO) for SEC filings and embeddings."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl: int = 3600,
        minio_endpoint: str | None = None,
        minio_access_key: str | None = None,
        minio_secret_key: str | None = None,
    ):
        """Initialize SEC filings cache with Redis + MinIO.

        Args:
            redis_url: Redis connection URL
            ttl: Time-to-live in seconds for Redis (default: 1 hour)
            minio_endpoint: MinIO endpoint URL
            minio_access_key: MinIO access key
            minio_secret_key: MinIO secret key
        """
        self.redis_url = redis_url
        self.ttl = ttl  # 1 hour default
        self.redis_client = None
        self._redis_available = None

        # MinIO configuration
        self.minio_endpoint = minio_endpoint or os.getenv(
            "MINIO_ENDPOINT", "http://minio:9000"
        )
        self.minio_access_key = minio_access_key or os.getenv(
            "MINIO_ACCESS_KEY", "minioadmin"
        )
        self.minio_secret_key = minio_secret_key or os.getenv(
            "MINIO_SECRET_KEY", "minioadmin"
        )
        self.minio_bucket = "research-sec-filings"
        self.s3_client = None
        self._minio_available = None

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

    def _get_s3_client(self):
        """Get S3 client with connection health check."""
        if self.s3_client is None and self._minio_available is None:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.minio_endpoint,
                    aws_access_key_id=self.minio_access_key,
                    aws_secret_access_key=self.minio_secret_key,
                )
                # Create bucket if doesn't exist
                try:
                    self.s3_client.head_bucket(Bucket=self.minio_bucket)
                except:
                    self.s3_client.create_bucket(Bucket=self.minio_bucket)
                    logger.info(f"Created MinIO bucket: {self.minio_bucket}")

                self._minio_available = True
                logger.info(f"SEC cache connected to MinIO at {self.minio_endpoint}")
            except Exception as e:
                logger.warning(
                    f"SEC cache: MinIO connection failed: {e}. MinIO caching disabled."
                )
                self._minio_available = False
                self.s3_client = None

        return self.s3_client if self._minio_available else None

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
        """Get cached SEC filings and embeddings (Redis first, MinIO fallback).

        Args:
            company_identifier: Ticker or CIK

        Returns:
            Cached data dict or None if not found
        """
        cache_key = self._get_cache_key(company_identifier)

        # Try Redis first (fastest)
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                cached_bytes = await redis_client.get(cache_key)
                if cached_bytes:
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
                        f"✅ SEC Redis cache hit for {company_identifier} "
                        f"({cached_data.get('total_chunks', 0)} chunks)"
                    )
                    return cached_data
            except Exception as e:
                logger.warning(f"SEC Redis retrieval failed: {e}")

        # Try MinIO fallback
        s3_client = self._get_s3_client()
        if s3_client:
            try:
                today = datetime.now(UTC).strftime("%Y-%m-%d")
                s3_key = f"{company_identifier.upper()}_{today}.json"

                response = s3_client.get_object(Bucket=self.minio_bucket, Key=s3_key)
                cached_str = response["Body"].read().decode("utf-8")
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
                    f"✅ SEC MinIO cache hit for {company_identifier} "
                    f"({cached_data.get('total_chunks', 0)} chunks)"
                )

                # Re-cache in Redis for fast access
                if redis_client:
                    cache_bytes = json.dumps(cached_data).encode("utf-8")
                    await redis_client.setex(cache_key, self.ttl, cache_bytes)

                return cached_data
            except Exception as e:
                if "NoSuchKey" not in str(e):
                    logger.warning(f"SEC MinIO retrieval failed: {e}")

        logger.debug(f"SEC cache miss for {company_identifier}")
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
        """Cache SEC filings data and embeddings (Redis + MinIO dual cache).

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
        cache_key = self._get_cache_key(company_identifier)

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

        cache_bytes = json.dumps(cache_data).encode("utf-8")
        cached_redis = False
        cached_minio = False

        # Cache in Redis (fast access)
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                await redis_client.setex(cache_key, self.ttl, cache_bytes)
                cached_redis = True
                logger.info(
                    f"✅ Cached SEC filings to Redis for {company_identifier} "
                    f"({len(chunks)} chunks, {len(cache_bytes):,} bytes)"
                )
            except Exception as e:
                logger.warning(f"Failed to cache to Redis: {e}")

        # Cache in MinIO (long-term storage)
        s3_client = self._get_s3_client()
        if s3_client:
            try:
                today = datetime.now(UTC).strftime("%Y-%m-%d")
                s3_key = f"{company_identifier.upper()}_{today}.json"

                s3_client.put_object(
                    Bucket=self.minio_bucket,
                    Key=s3_key,
                    Body=cache_bytes,
                    ContentType="application/json",
                )
                cached_minio = True
                logger.info(
                    f"✅ Cached SEC filings to MinIO for {company_identifier} "
                    f"({len(cache_bytes):,} bytes)"
                )
            except Exception as e:
                logger.warning(f"Failed to cache to MinIO: {e}")

        return cached_redis or cached_minio

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
