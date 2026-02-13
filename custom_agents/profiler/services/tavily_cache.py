"""Tavily search and scrape caching service using MinIO.

Caches web search results and scraped page content to reduce API costs
and speed up repeated searches.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class TavilyCacheService:
    """Cache Tavily search results and scraped pages in MinIO."""

    def __init__(self):
        """Initialize cache service with MinIO configuration."""
        self.s3_endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
        self.s3_access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.s3_secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.bucket = os.getenv("TAVILY_CACHE_BUCKET", "tavily-cache")
        self.scrape_ttl_days = int(os.getenv("TAVILY_SCRAPE_TTL_DAYS", "7"))
        self.search_ttl_days = int(os.getenv("TAVILY_SEARCH_TTL_DAYS", "1"))
        self._s3_client = None

    def _get_s3_client(self):
        """Get or create S3 client with bucket initialization."""
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.s3_endpoint,
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
            )
            # Ensure bucket exists
            try:
                self._s3_client.head_bucket(Bucket=self.bucket)
            except ClientError:
                try:
                    self._s3_client.create_bucket(Bucket=self.bucket)
                    logger.info(f"Created Tavily cache bucket: {self.bucket}")
                except Exception as e:
                    logger.warning(f"Could not create Tavily cache bucket: {e}")
        return self._s3_client

    def _hash_key(self, value: str) -> str:
        """Generate a short hash for cache keys."""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _get_scrape_key(self, url: str) -> str:
        """Generate cache key for scraped URL content."""
        url_hash = self._hash_key(url)
        # Extract domain for organization
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace(".", "_")
        return f"scrape/{domain}/{url_hash}.json"

    def _get_search_key(self, query: str) -> str:
        """Generate cache key for search results."""
        query_hash = self._hash_key(query.lower().strip())
        return f"search/{query_hash}.json"

    def _is_expired(self, cached_at: str, ttl_days: int) -> bool:
        """Check if cached data has expired."""
        try:
            cached_time = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - cached_time).days
            return age_days >= ttl_days
        except Exception:
            return True  # Treat parse errors as expired

    def get_scraped_content(self, url: str) -> dict[str, Any] | None:
        """Get cached scraped content for a URL.

        Args:
            url: The URL to look up

        Returns:
            Cached data dict or None if not found/expired
        """
        try:
            s3 = self._get_s3_client()
            key = self._get_scrape_key(url)
            response = s3.get_object(Bucket=self.bucket, Key=key)
            data = json.loads(response["Body"].read().decode("utf-8"))

            # Check TTL
            if self._is_expired(data.get("cached_at", ""), self.scrape_ttl_days):
                logger.debug(f"Cache EXPIRED for scrape: {url[:50]}...")
                return None

            logger.info(f"📦 Cache HIT for scrape: {url[:50]}...")
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.debug(f"Cache MISS for scrape: {url[:50]}...")
            else:
                logger.warning(f"Cache error for scrape {url[:50]}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to read scrape cache: {e}")
            return None

    def save_scraped_content(
        self, url: str, content: str, title: str = "", metadata: dict | None = None
    ) -> None:
        """Save scraped content to cache.

        Args:
            url: Source URL
            content: Raw scraped content
            title: Page title
            metadata: Additional metadata
        """
        try:
            s3 = self._get_s3_client()
            key = self._get_scrape_key(url)

            cache_data = {
                "url": url,
                "content": content,
                "title": title,
                "metadata": metadata or {},
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "content_length": len(content),
            }

            s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(cache_data, default=str).encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"💾 Cached scrape: {url[:50]}... ({len(content):,} chars)")
        except Exception as e:
            logger.warning(f"Failed to cache scraped content for {url[:50]}: {e}")

    def get_search_results(self, query: str) -> dict[str, Any] | None:
        """Get cached search results for a query.

        Args:
            query: Search query string

        Returns:
            Cached results dict or None if not found/expired
        """
        try:
            s3 = self._get_s3_client()
            key = self._get_search_key(query)
            response = s3.get_object(Bucket=self.bucket, Key=key)
            data = json.loads(response["Body"].read().decode("utf-8"))

            # Check TTL
            if self._is_expired(data.get("cached_at", ""), self.search_ttl_days):
                logger.debug(f"Cache EXPIRED for search: {query[:50]}...")
                return None

            logger.info(f"📦 Cache HIT for search: {query[:50]}...")
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.debug(f"Cache MISS for search: {query[:50]}...")
            else:
                logger.warning(f"Cache error for search {query[:50]}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to read search cache: {e}")
            return None

    def save_search_results(
        self, query: str, results: list[dict], max_results: int = 10
    ) -> None:
        """Save search results to cache.

        Args:
            query: Search query string
            results: List of search result dicts
            max_results: Number of results requested
        """
        try:
            s3 = self._get_s3_client()
            key = self._get_search_key(query)

            cache_data = {
                "query": query,
                "results": results,
                "max_results": max_results,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "result_count": len(results),
            }

            s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(cache_data, default=str).encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"💾 Cached search: {query[:50]}... ({len(results)} results)")
        except Exception as e:
            logger.warning(f"Failed to cache search results for {query[:50]}: {e}")


# Singleton instance
_cache_service: TavilyCacheService | None = None


def get_tavily_cache() -> TavilyCacheService:
    """Get singleton Tavily cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = TavilyCacheService()
    return _cache_service
