"""Type definitions for InsightMesh bot.

This module provides TypedDict classes to replace dict[str, Any] types
throughout the codebase, improving type safety and IDE support.
"""

from typing import Any, NotRequired, TypedDict


class ChunkMetadata(TypedDict, total=False):
    """Metadata attached to a context chunk from vector search.

    All fields are optional as different sources may provide different metadata.
    """

    # Common fields
    file_name: str  # Name of the source file/document
    source: str  # Source type (e.g., "uploaded_document", "gdrive", etc.)
    text: str  # Original text content (may duplicate "content" field)

    # Document identification
    chunk_id: str  # Unique chunk identifier
    document_id: str  # Parent document identifier

    # File metadata
    file_path: str  # Full path to the file
    file_type: str  # MIME type or file extension
    file_size: int  # File size in bytes

    # Chunking information
    chunk_index: int  # Position of this chunk in the document
    total_chunks: int  # Total number of chunks from this document

    # Timestamps
    created_at: str  # When document was created/uploaded
    modified_at: str  # When document was last modified
    indexed_at: str  # When document was indexed

    # Permissions and ownership
    owner: str  # Document owner
    permissions: dict[str, Any]  # Permission settings

    # Vector database metadata
    namespace: str  # Qdrant namespace
    collection: str  # Collection name

    # Additional arbitrary metadata
    # (TypedDict doesn't support arbitrary keys, so callers can add extra fields)


class ContextChunk(TypedDict):
    """A chunk of context retrieved from vector search or uploaded documents.

    Used throughout RAG pipeline for context augmentation.
    """

    content: str  # The actual text content of the chunk
    similarity: float  # Similarity score (0-1, higher is better)
    metadata: ChunkMetadata  # Metadata about the chunk source
    id: NotRequired[str | int]  # Optional document/chunk ID
    namespace: NotRequired[str]  # Optional namespace (e.g., "default", "metric")


class AgentMetadata(TypedDict, total=False):
    """Metadata returned by agent execution.

    All fields are optional as different agents may return different metadata.
    """

    # Thread management
    clear_thread_tracking: bool  # If True, clear thread tracking after execution

    # Agent execution info
    agent_name: str  # Name of the agent that was executed
    execution_time: float  # Execution time in seconds
    model_used: str  # LLM model used for generation

    # Token usage
    prompt_tokens: int  # Number of prompt tokens used
    completion_tokens: int  # Number of completion tokens used
    total_tokens: int  # Total tokens used

    # Tool usage
    tools_used: list[str]  # List of tools/functions called
    tool_results: dict[str, Any]  # Results from tool calls

    # Error handling
    error: str  # Error message if execution failed
    partial_response: bool  # If True, response is incomplete due to error

    # Citations and sources
    sources: list[str]  # List of source documents used
    citations: list[dict[str, Any]]  # Citation information

    # Additional arbitrary metadata


class AgentResponse(TypedDict):
    """Response from agent execution via HTTP API.

    This is the structure returned by agent-service HTTP endpoints.
    """

    response: str  # The agent's text response
    metadata: AgentMetadata  # Additional metadata from agent execution


class AgentContext(TypedDict, total=False):
    """Context dictionary passed to agents for execution.

    All fields are optional as different invocations may provide different context.
    Note: Non-serializable fields (slack_service, llm_service, conversation_cache)
    are filtered out before sending to agent-service via HTTP.
    """

    # Slack context (serializable)
    user_id: str  # Slack user ID
    channel: str  # Slack channel ID
    thread_ts: str  # Thread timestamp for threading
    thinking_ts: str  # Timestamp of thinking indicator message

    # Document context
    document_content: str  # Content of uploaded document
    files: list[dict[str, Any]]  # List of uploaded files
    file_names: list[str]  # Names of uploaded files

    # Service instances (non-serializable, filtered before HTTP send)
    slack_service: Any  # SlackService instance (filtered out)
    llm_service: Any  # LLMService instance (filtered out)
    conversation_cache: Any  # Cache instance (filtered out)

    # Additional context fields can be added by callers


class AgentInfo(TypedDict):
    """Information about a registered agent.

    Used by agent registry to track available agents and their capabilities.
    """

    name: str  # Agent name/identifier
    display_name: str  # Human-readable display name
    description: str  # Description of agent capabilities
    tags: NotRequired[list[str]]  # Optional tags for categorization
    enabled: NotRequired[bool]  # Whether agent is currently enabled


class CircuitBreakerStatus(TypedDict):
    """Status of circuit breaker for monitoring.

    Used by agent client to track circuit breaker health.
    """

    state: str  # Circuit breaker state: "closed", "open", or "half-open"
    failure_count: int  # Number of consecutive failures
    last_failure_time: float | None  # Timestamp of last failure (None if no failures)
    last_success_time: float | None  # Timestamp of last success (None if no successes)


class ContextQuality(TypedDict):
    """Validation results for context quality.

    Used to assess the quality of retrieved context chunks.
    """

    passed: bool  # Whether context meets quality thresholds
    average_similarity: float  # Average similarity score across chunks
    min_similarity: float  # Minimum similarity score observed
    max_similarity: float  # Maximum similarity score observed
    chunk_count: int  # Number of chunks evaluated
    warnings: list[str]  # List of quality warnings


class TimeRange(TypedDict, total=False):
    """Time range for query filtering.

    Used in query intent classification and rewriting.
    """

    start: str | None  # Start date in YYYY-MM-DD format or None
    end: str | None  # End date in YYYY-MM-DD format or None


class QueryIntent(TypedDict):
    """Query intent classification result.

    Used by adaptive query rewriter to determine rewriting strategy.
    """

    type: str  # Intent type: "team_allocation", "project_info", "client_info", "document_search", "general"
    entities: list[
        str
    ]  # Extracted entities (project names, client names, person names)
    time_range: TimeRange  # Optional time range for filtering
    confidence: float  # Confidence score (0.0-1.0)


class QueryRewriteResult(TypedDict):
    """Result from query rewriting operation.

    Contains the rewritten query, filters, and strategy used.
    """

    query: str  # Rewritten query text
    filters: dict[
        str, Any
    ]  # Filter criteria for vector search (record_type, dates, etc.)
    strategy: (
        str  # Rewriting strategy used: "hyde", "semantic", "expand", "lightweight"
    )


class QueryRewriterStats(TypedDict):
    """Statistics from query rewriter operations.

    Used for monitoring and debugging query rewriting performance.
    """

    total_queries: int  # Total number of queries rewritten
    strategy_counts: dict[str, int]  # Count of each strategy used
    avg_confidence: float  # Average confidence score
    cache_hits: NotRequired[int]  # Optional cache hit count
    cache_misses: NotRequired[int]  # Optional cache miss count


# Export all types
__all__ = [
    "ChunkMetadata",
    "ContextChunk",
    "AgentMetadata",
    "AgentResponse",
    "AgentContext",
    "AgentInfo",
    "CircuitBreakerStatus",
    "ContextQuality",
    "TimeRange",
    "QueryIntent",
    "QueryRewriteResult",
    "QueryRewriterStats",
]
