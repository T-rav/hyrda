"""Pydantic models for retrieval API requests and responses."""

from typing import Any

from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    """Request model for retrieval API."""

    query: str = Field(..., min_length=1, description="Search query")
    user_id: str = Field(
        default="agent@system", description="User ID for tracing and permissions"
    )
    system_message: str | None = Field(
        default=None,
        description="Custom context for filtering (e.g., permissions, role, accessible projects)",
    )
    max_chunks: int = Field(
        default=10, ge=1, le=20, description="Maximum chunks to return (1-20)"
    )
    similarity_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum similarity score (0.0-1.0)"
    )
    filters: dict[str, Any] | None = Field(
        default=None, description="Metadata filters for Qdrant"
    )
    conversation_history: list[dict[str, str]] | None = Field(
        default=None, description="Conversation context for query rewriting"
    )
    enable_query_rewriting: bool = Field(
        default=True, description="Enable query rewriting for better retrieval"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "query": "8th Light company profile",
                "user_id": "analyst@example.com",
                "max_chunks": 10,
                "similarity_threshold": 0.7,
                "enable_query_rewriting": True,
            }
        }


class Chunk(BaseModel):
    """Single retrieved chunk with content and metadata."""

    content: str = Field(..., description="Chunk text content")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Chunk metadata (source, file_name, etc.)"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "content": "8th Light is a software consultancy...",
                "similarity": 0.92,
                "metadata": {
                    "file_name": "8th_light_profile.pdf",
                    "source": "internal_docs",
                    "page": 1,
                },
            }
        }


class RetrievalMetadata(BaseModel):
    """Metadata about the retrieval operation."""

    total_chunks: int = Field(..., description="Number of chunks returned")
    unique_sources: int = Field(..., description="Number of unique source documents")
    avg_similarity: float = Field(
        ..., ge=0.0, le=1.0, description="Average similarity score"
    )
    similarity_threshold: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity threshold used"
    )
    query_rewritten: bool = Field(..., description="Whether query was rewritten")
    service: str = Field(
        default="rag-service", description="Service that handled request"
    )


class RetrievalResponse(BaseModel):
    """Response from retrieval API."""

    chunks: list[Chunk] = Field(default_factory=list, description="Retrieved chunks")
    metadata: RetrievalMetadata = Field(..., description="Retrieval operation metadata")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "chunks": [
                    {
                        "content": "8th Light is a software consultancy...",
                        "similarity": 0.92,
                        "metadata": {"file_name": "8th_light_profile.pdf"},
                    }
                ],
                "metadata": {
                    "total_chunks": 1,
                    "unique_sources": 1,
                    "avg_similarity": 0.92,
                    "similarity_threshold": 0.7,
                    "query_rewritten": True,
                    "service": "rag-service",
                },
            }
        }
