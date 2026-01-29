"""
Retrieval-only API endpoint for agents and services.

This endpoint provides JUST the RAG retrieval without LLM generation,
allowing agents to:
1. Get relevant chunks from vector DB
2. Apply custom filters (permissions, metadata)
3. Use system_message for contextual retrieval
4. Call their own LLM with the chunks

Benefits:
- Single source of truth for vector access
- Centralized permissions and filtering
- Traceability (all retrievals logged)
- No direct Qdrant dependency for agents
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from config.settings import get_settings
from dependencies.auth import require_service_auth
from providers.embedding.factory import create_embedding_provider
from services.langfuse_service import get_langfuse_service
from services.retrieval_service import get_retrieval_service
from services.vector_service import create_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["retrieve"])


# Request/Response Models


class RetrieveRequest(BaseModel):
    """Request model for retrieval-only operations."""

    query: str = Field(..., description="Search query")
    user_id: str | None = Field(None, description="User ID for filtering and tracing")
    system_message: str | None = Field(
        None,
        description=(
            "Custom context for retrieval filtering. "
            "Use to inject: user permissions, accessible projects, role-based filters. "
            "Example: 'User: john@8thlight.com\\nRole: consultant\\nProjects: A, B, C'"
        ),
    )
    max_chunks: int = Field(5, ge=1, le=20, description="Maximum chunks to return (1-20)")
    similarity_threshold: float = Field(
        0.7, ge=0.0, le=1.0, description="Minimum similarity score (0.0-1.0)"
    )
    filters: dict[str, Any] | None = Field(
        None,
        description=(
            "Metadata filters for Qdrant. "
            "Example: {'source': 'google_drive', 'project': 'Project A'}"
        ),
    )
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Conversation history for query rewriting context",
    )
    enable_query_rewriting: bool = Field(
        True, description="Enable query rewriting for better retrieval"
    )


class RetrievalChunk(BaseModel):
    """Retrieved chunk with metadata."""

    content: str = Field(..., description="Chunk text content")
    metadata: dict[str, Any] = Field(..., description="Chunk metadata")
    similarity: float = Field(..., description="Similarity score")
    chunk_id: str | None = Field(None, description="Unique chunk identifier")


class RetrieveResponse(BaseModel):
    """Response model for retrieval-only operations."""

    chunks: list[RetrievalChunk] = Field(..., description="Retrieved chunks with metadata")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Retrieval metadata: total_chunks, unique_sources, "
            "avg_similarity, query_rewritten, etc."
        ),
    )


# Endpoints


@router.post("/v1/retrieve", response_model=RetrieveResponse)
@router.post("/retrieve", response_model=RetrieveResponse)  # Alias
async def retrieve_chunks(
    request: RetrieveRequest,
    service: dict = Depends(require_service_auth),
):
    """
    Retrieve relevant chunks from vector database without LLM generation.

    This endpoint is designed for agents and services that want:
    - RAG retrieval only (no LLM call)
    - Custom filtering based on permissions/context
    - Direct access to chunks for their own processing

    Use cases:
    - Agents that call LLMs directly in their graph
    - Services that need document search without generation
    - Custom RAG pipelines with their own LLM logic

    The endpoint:
    1. Optionally rewrites query for better retrieval
    2. Searches vector database with filters
    3. Returns chunks with metadata and similarity scores
    4. Traces retrieval to Langfuse for observability

    Args:
        request: Retrieval request with query and filters
        service: Service info from authentication (injected)

    Returns:
        RetrieveResponse with chunks and metadata

    Raises:
        HTTPException: 500 if retrieval fails
    """
    service_name = service.get("service", "unknown")
    logger.info(
        f"[{service_name}] Retrieve request: query='{request.query[:50]}...', "
        f"max_chunks={request.max_chunks}, user_id={request.user_id}"
    )

    try:
        # Get services
        settings = get_settings()
        retrieval_service = get_retrieval_service()
        vector_store = create_vector_store(settings.vector)
        embedding_service = create_embedding_provider(settings.embedding)

        # Get langfuse for tracing
        langfuse_service = get_langfuse_service()
        trace = None
        if langfuse_service:
            trace = langfuse_service.start_trace(
                name="retrieve_chunks",
                user_id=request.user_id,
                metadata={
                    "service": service_name,
                    "query": request.query,
                    "max_chunks": request.max_chunks,
                    "similarity_threshold": request.similarity_threshold,
                    "has_filters": request.filters is not None,
                    "has_system_message": request.system_message is not None,
                },
            )

        # Perform retrieval using retrieve_context
        context_chunks = await retrieval_service.retrieve_context(
            query=request.query,
            vector_service=vector_store,
            embedding_service=embedding_service,
            conversation_history=request.conversation_history,
            user_id=request.user_id,
        )

        # Convert ContextChunk objects to dicts for response
        chunks = []
        for context_chunk in context_chunks:
            chunks.append(
                {
                    "content": context_chunk.content,
                    "similarity": context_chunk.similarity,
                    "metadata": context_chunk.metadata,
                }
            )

        # Build response metadata
        unique_sources = set()
        total_similarity = 0.0
        for chunk in chunks:
            if "file_name" in chunk.get("metadata", {}):
                unique_sources.add(chunk["metadata"]["file_name"])
            total_similarity += chunk.get("similarity", 0.0)

        avg_similarity = total_similarity / len(chunks) if chunks else 0.0

        response_metadata = {
            "total_chunks": len(chunks),
            "unique_sources": len(unique_sources),
            "avg_similarity": round(avg_similarity, 3),
            "similarity_threshold": request.similarity_threshold,
            "query_rewritten": request.enable_query_rewriting,
            "service": service_name,
        }

        # Trace to Langfuse
        if trace and langfuse_service:
            langfuse_service.end_trace(
                trace,
                output={
                    "chunks_count": len(chunks),
                    "unique_sources": len(unique_sources),
                    "avg_similarity": avg_similarity,
                },
            )

        # Format response
        response_chunks = [
            RetrievalChunk(
                content=chunk["content"],
                metadata=chunk.get("metadata", {}),
                similarity=chunk.get("similarity", 0.0),
                chunk_id=chunk.get("chunk_id"),
            )
            for chunk in chunks
        ]

        logger.info(
            f"✅ Retrieved {len(chunks)} chunks from {len(unique_sources)} sources "
            f"(avg similarity: {avg_similarity:.3f})"
        )

        return RetrieveResponse(chunks=response_chunks, metadata=response_metadata)

    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        if trace and langfuse_service:
            langfuse_service.end_trace(trace, error=str(e))

        from fastapi import HTTPException

        raise HTTPException(
            status_code=500,
            detail=f"Retrieval failed: {str(e)}",
        ) from e
