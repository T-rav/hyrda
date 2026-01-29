"""Typed data models for the AI Slack Bot application."""

# Database models
from .base import Base

# File processing models
from .file_processing import (
    DocumentChunk,
    EmbeddingResult,
    FileMetadata,
    FileType,
    ProcessingResult,
    ProcessingStatus,
    SlackFileInfo,
)
from .librechat_usage import LibreChatUsage

# LLM interaction models
from .llm_interactions import (
    ConversationContext,
    ConversationMessage,
    GenerationRequest,
    GenerationResponse,
    LLMResponse,
    LLMUsage,
    MessageRole,
    RAGContext,
)

# Retrieval and search models
from .retrieval import (
    IndexingOperation,
    RetrievalConfig,
    RetrievalMethod,
    RetrievalResult,
    SearchQuery,
    SearchResponse,
    SearchType,
    VectorStoreStats,
)

# Service response models
from .service_responses import (
    ApiResponse,
    CacheStats,
    HealthCheckResponse,
    MetricsData,
    PerformanceMetrics,
    SystemStatus,
    ThreadInfo,
    UsageMetrics,
)

# Slack event models
from .slack_events import (
    MessageSubtype,
    SlackChannel,
    SlackEvent,
    SlackEventType,
    SlackMessage,
    SlackResponse,
    SlackUser,
    ThreadContext,
)
from .slack_usage import SlackUsage
from .slack_user import SlackUser as SlackUserDB

__all__ = [
    # Database models
    "Base",
    "LibreChatUsage",
    "SlackUsage",
    "SlackUserDB",
    # Service responses
    "ApiResponse",
    "CacheStats",
    "HealthCheckResponse",
    "MetricsData",
    "PerformanceMetrics",
    "SystemStatus",
    "ThreadInfo",
    "UsageMetrics",
    # File processing
    "DocumentChunk",
    "EmbeddingResult",
    "FileMetadata",
    "FileType",
    "ProcessingResult",
    "ProcessingStatus",
    "SlackFileInfo",
    # LLM interactions
    "ConversationContext",
    "ConversationMessage",
    "GenerationRequest",
    "GenerationResponse",
    "LLMResponse",
    "LLMUsage",
    "MessageRole",
    "RAGContext",
    # Retrieval
    "IndexingOperation",
    "RetrievalConfig",
    "RetrievalMethod",
    "RetrievalResult",
    "SearchQuery",
    "SearchResponse",
    "SearchType",
    "VectorStoreStats",
    # Slack events
    "MessageSubtype",
    "SlackChannel",
    "SlackEvent",
    "SlackEventType",
    "SlackMessage",
    "SlackResponse",
    "SlackUser",
    "ThreadContext",
]
