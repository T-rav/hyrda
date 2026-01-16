"""Shared HTTP clients for service-to-service communication."""

from .config import RetrievalClientConfig
from .exceptions import (
    RetrievalAuthError,
    RetrievalConnectionError,
    RetrievalError,
    RetrievalServiceError,
    RetrievalTimeoutError,
    RetrievalValidationError,
)
from .models import Chunk, RetrievalMetadata, RetrievalRequest, RetrievalResponse
from .retrieval_client import RetrievalClient, get_retrieval_client

__all__ = [
    # Client
    "RetrievalClient",
    "get_retrieval_client",
    # Config
    "RetrievalClientConfig",
    # Models
    "RetrievalRequest",
    "RetrievalResponse",
    "Chunk",
    "RetrievalMetadata",
    # Exceptions
    "RetrievalError",
    "RetrievalAuthError",
    "RetrievalTimeoutError",
    "RetrievalValidationError",
    "RetrievalServiceError",
    "RetrievalConnectionError",
]
