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
