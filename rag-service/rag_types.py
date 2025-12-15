"""Type definitions for RAG service."""

from typing import Any, TypedDict


class AgentContext(TypedDict, total=False):
    """Context passed to agents."""

    user_id: str | None
    conversation_id: str | None
    session_id: str | None
    channel: str | None
    thread_ts: str | None
    document_content: str | None
    document_filename: str | None
    files: list[dict] | None
    file_names: list[str] | None


class AgentInfo(TypedDict):
    """Agent metadata."""

    name: str
    description: str
    aliases: list[str]


class AgentResponse(TypedDict):
    """Agent execution response."""

    response: str
    metadata: dict[str, Any]


class CircuitBreakerStatus(TypedDict):
    """Circuit breaker status."""

    state: str
    failure_count: int
    success_count: int
    last_failure_time: float | None
    is_open: bool


class HealthStatus(TypedDict):
    """Health check status."""

    status: str
    checks: dict[str, Any]


class ContextChunk(TypedDict):
    """Retrieved context chunk from vector database."""

    content: str
    score: float
    metadata: dict[str, Any]


class ContextQuality(TypedDict):
    """Context quality metrics."""

    relevance_score: float
    chunk_count: int
    avg_score: float


class QueryIntent(TypedDict):
    """Query intent classification."""

    intent: str
    confidence: float
    entities: list[str]


class QueryRewriteResult(TypedDict):
    """Query rewrite result."""

    original_query: str
    rewritten_query: str
    changed: bool


class QueryRewriterStats(TypedDict):
    """Query rewriter statistics."""

    total_rewrites: int
    avg_improvement: float


class WebSearchResult(TypedDict):
    """Web search result."""

    title: str
    url: str
    snippet: str
    score: float


class WebScrapeResult(TypedDict):
    """Web scrape result."""

    url: str
    content: str
    success: bool
    error: str | None


class DeepResearchResult(TypedDict):
    """Deep research result."""

    query: str
    summary: str
    sources: list[dict[str, Any]]
    confidence: float


class PromptInfo(TypedDict):
    """Prompt metadata."""

    name: str
    template: str
    variables: list[str]
