"""Typed models for LLM interactions and conversations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(str, Enum):
    """Message roles in conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


class ConversationMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_count: int | None = None
    function_call: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None

    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True)
class ConversationContext:
    messages: list[ConversationMessage]
    channel_id: str
    thread_id: str | None = None
    user_id: str | None = None
    total_tokens: int = 0
    max_tokens: int = 4000
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LLMUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None = None

    model_config = ConfigDict(frozen=True)


class LLMResponse(BaseModel):
    content: str
    model: str
    provider: Literal["openai", "anthropic", "ollama"]
    usage: LLMUsage | None = None
    response_time_ms: float
    finish_reason: str | None = None
    function_calls: list[dict[str, Any]] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True)
class RAGContext:
    chunks: list[str]
    sources: list[str]
    similarities: list[float]
    total_chunks: int
    retrieval_time_ms: float
    reranked: bool = False


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    system_message: str | None = None
    context: RAGContext | None = None
    max_tokens: int = 1000
    temperature: float = 0.7
    top_p: float = 0.9
    stop_sequences: list[str] | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class GenerationResponse:
    content: str
    llm_response: LLMResponse
    total_processing_time_ms: float
    context_used: RAGContext | None = None
    cached: bool = False
