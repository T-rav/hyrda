"""Configuration for retrieval client."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalClientConfig:
    """Configuration for retrieval client.

    All values have sensible defaults and can be overridden via constructor
    or environment variables.
    """

    # Service discovery
    base_url: str = "http://rag-service:8002"
    """rag-service URL (default: http://rag-service:8002)"""

    # Authentication
    service_token: str | None = None
    """Service authentication token (default: from RAG_SERVICE_TOKEN env var)"""

    default_user_id: str = "agent@system"
    """Default user ID when none provided"""

    # Timeouts (seconds)
    request_timeout: float = 30.0
    """HTTP request timeout in seconds"""

    connect_timeout: float = 5.0
    """HTTP connection timeout in seconds"""

    # Retrieval defaults
    default_max_chunks: int = 10
    """Default maximum chunks to return"""

    default_similarity_threshold: float = 0.7
    """Default minimum similarity score"""

    default_enable_query_rewriting: bool = True
    """Default: enable query rewriting for better retrieval"""

    # Optional features
    enable_cache: bool = False
    """Enable response caching (default: disabled)"""

    cache_ttl_seconds: int = 300
    """Cache TTL in seconds (default: 5 minutes)"""

    @classmethod
    def from_env(cls) -> "RetrievalClientConfig":
        """Create config from environment variables.

        Environment variables:
        - RAG_SERVICE_URL: rag-service base URL
        - RAG_SERVICE_TOKEN: service authentication token
        - RETRIEVAL_TIMEOUT: request timeout in seconds
        - RETRIEVAL_MAX_CHUNKS: default max chunks
        - RETRIEVAL_SIMILARITY_THRESHOLD: default similarity threshold
        - RETRIEVAL_ENABLE_CACHE: enable response caching (true/false)
        """
        return cls(
            base_url=os.getenv("RAG_SERVICE_URL", cls.base_url),
            service_token=os.getenv("RAG_SERVICE_TOKEN"),
            request_timeout=float(os.getenv("RETRIEVAL_TIMEOUT", cls.request_timeout)),
            default_max_chunks=int(
                os.getenv("RETRIEVAL_MAX_CHUNKS", cls.default_max_chunks)
            ),
            default_similarity_threshold=float(
                os.getenv(
                    "RETRIEVAL_SIMILARITY_THRESHOLD", cls.default_similarity_threshold
                )
            ),
            enable_cache=os.getenv("RETRIEVAL_ENABLE_CACHE", "false").lower() == "true",
        )
