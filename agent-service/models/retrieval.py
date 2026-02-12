"""Typed models for retrieval and search operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .file_processing import DocumentChunk


class RetrievalMethod(StrEnum):
    """Methods used for document retrieval."""

    DENSE = "dense"
    SPARSE = "sparse"
    CONTEXTUAL = "contextual"
    RERANKED = "reranked"


class SearchType(StrEnum):
    """Types of search operations."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    SIMILARITY = "similarity"


class RetrievalResult(BaseModel):
    """Enhanced retrieval result with comprehensive metadata."""

    content: str
    similarity: float
    chunk_id: str
    document_id: str
    source: RetrievalMethod
    rank: int | None = None
    rerank_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(frozen=True)

    @property
    def document_chunk(self) -> DocumentChunk | None:
        """Convert to DocumentChunk if metadata contains required fields."""
        if all(
            key in self.metadata for key in ["chunk_index", "start_char", "end_char"]
        ):
            # This would need to be implemented based on available metadata
            pass
        return None


@dataclass(frozen=True)
class SearchQuery:
    """Structured search query with parameters."""

    text: str
    search_type: SearchType = SearchType.SEMANTIC
    max_results: int = 10
    similarity_threshold: float = 0.7
    filters: dict[str, Any] | None = None
    boost_factors: dict[str, float] | None = None
    rerank: bool = False
    include_metadata: bool = True


@dataclass(frozen=True)
class SearchResponse:
    """Complete search response with timing and metadata."""

    query: SearchQuery
    results: list[RetrievalResult]
    total_found: int
    search_time_ms: float
    method_used: RetrievalMethod
    rerank_time_ms: float | None = None
    debug_info: dict[str, Any] | None = None


@dataclass(frozen=True)
class VectorStoreStats:
    """Vector store statistics and health information."""

    total_documents: int
    total_chunks: int
    index_size_mb: float
    dimensions: int
    last_updated: datetime
    health_status: str
    memory_usage_mb: float | None = None
    query_latency_ms: float | None = None
    index_type: str | None = None


@dataclass(frozen=True)
class IndexingOperation:
    """Document indexing operation result."""

    documents_processed: int
    chunks_created: int
    embeddings_generated: int
    indexing_time_ms: float
    errors: list[str] | None = None
    warnings: list[str] | None = None
    batch_id: str | None = None


@dataclass(frozen=True)
class RetrievalConfig:
    """Configuration for retrieval operations."""

    max_chunks: int = 5
    similarity_threshold: float = 0.7
    rerank_enabled: bool = False
    rerank_top_k: int = 20
    dense_weight: float = 0.5
    sparse_weight: float = 0.5
    include_metadata: bool = True
    filter_duplicates: bool = True
    boost_recent: bool = False
