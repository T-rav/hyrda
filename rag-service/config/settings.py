"""RAG Service configuration settings."""

from pydantic import ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings


class LLMSettings(BaseSettings):
    """LLM API settings"""

    provider: str = Field(default="openai", description="LLM provider (only 'openai' is supported)")
    api_key: SecretStr = Field(description="LLM API key")
    model: str = Field(default="gpt-4o-mini", description="LLM model name")
    base_url: str | None = Field(
        default=None, description="Custom base URL (for OpenAI-compatible APIs)"
    )
    temperature: float = Field(default=0.7, description="Response temperature")
    max_tokens: int = Field(default=2000, description="Maximum response tokens")

    model_config = ConfigDict(env_prefix="LLM_")  # type: ignore[assignment,typeddict-unknown-key]


class ConversationSettings(BaseSettings):
    """Conversation context management settings"""

    max_messages: int = Field(
        default=20,
        description="Maximum messages to keep in conversation context (sliding window)",
    )
    keep_recent: int = Field(
        default=4,
        description="Number of recent messages to keep when summarizing",
    )
    summarize_threshold: float = Field(
        default=0.75,
        description="Context usage percentage to trigger summarization (0.75 = 75%)",
    )
    model_context_window: int = Field(
        default=128000,
        description="Model's maximum context window in tokens (default: 128k for GPT-4o)",
    )

    model_config = ConfigDict(env_prefix="CONVERSATION_")  # type: ignore[assignment,typeddict-unknown-key]


class CacheSettings(BaseSettings):
    """Redis cache settings"""

    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    conversation_ttl: int = Field(
        default=1800, description="Conversation cache TTL in seconds (30 minutes)"
    )
    enabled: bool = Field(default=True, description="Enable conversation caching")

    model_config = ConfigDict(env_prefix="CACHE_")  # type: ignore[assignment,typeddict-unknown-key]


class DatabaseSettings(BaseSettings):
    """MySQL database settings"""

    url: str | None = Field(
        default=None,
        description="MySQL connection URL (required if enabled=True)",
        validation_alias="DATA_DATABASE_URL",  # Support both DATABASE_URL and DATA_DATABASE_URL
    )
    enabled: bool = Field(default=False, description="Enable database features")

    model_config = ConfigDict(env_prefix="DATABASE_", populate_by_name=True)  # type: ignore[assignment,typeddict-unknown-key]


class VectorSettings(BaseSettings):
    """Vector database settings for RAG (Qdrant)"""

    enabled: bool = Field(default=True, description="Enable vector database features")
    provider: str = Field(default="qdrant", description="Vector database provider (qdrant)")
    collection_name: str = Field(
        default="insightmesh-knowledge-base", description="Collection name"
    )
    host: str = Field(default="qdrant", description="Qdrant host (docker service name)")
    port: int = Field(default=6333, description="Qdrant REST API port")
    api_key: str | None = Field(
        default=None, description="Qdrant API key for authentication (optional)"
    )

    model_config = ConfigDict(env_prefix="VECTOR_")  # type: ignore[assignment,typeddict-unknown-key]


class EmbeddingSettings(BaseSettings):
    """Embedding model settings"""

    provider: str = Field(
        default="openai",
        description="Embedding provider (openai, sentence-transformers)",
    )
    model: str = Field(default="text-embedding-3-small", description="Embedding model name")
    api_key: SecretStr | None = Field(
        default=None, description="Embedding API key (uses LLM key if None)"
    )
    chunk_size: int = Field(default=1000, description="Text chunk size for embedding")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks")

    model_config = ConfigDict(env_prefix="EMBEDDING_")  # type: ignore[assignment,typeddict-unknown-key]


class RAGSettings(BaseSettings):
    """RAG retrieval settings"""

    max_chunks: int = Field(default=5, description="Maximum chunks to retrieve")
    similarity_threshold: float = Field(default=0.35, description="Minimum similarity score")
    max_results: int = Field(default=5, description="Maximum final results to return")
    results_similarity_threshold: float = Field(
        default=0.5, description="Final results minimum similarity threshold"
    )
    include_metadata: bool = Field(default=True, description="Include document metadata in context")
    entity_content_boost: float = Field(
        default=0.05,
        description="Similarity boost per entity found in document content (0.05 = 5%)",
    )
    entity_title_boost: float = Field(
        default=0.1,
        description="Similarity boost per entity found in document title/filename (0.1 = 10%)",
    )
    max_chunks_per_document: int = Field(
        default=3,
        description="Maximum chunks to return from a single document (prevents one doc from dominating results)",
    )
    enable_query_rewriting: bool = Field(
        default=True,
        description="Enable adaptive query rewriting to improve retrieval accuracy (adds 1-2 LLM calls per search)",
    )
    query_rewrite_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model to use for query rewriting (fast model recommended)",
    )

    model_config = ConfigDict(env_prefix="RAG_")  # type: ignore[assignment,typeddict-unknown-key]


class SearchSettings(BaseSettings):
    """Search and research API settings"""

    # Tavily settings
    tavily_api_key: str | None = Field(
        default=None,
        description="Tavily API key for web search and scraping",
        alias="TAVILY_API_KEY",
    )

    # Perplexity settings
    perplexity_api_key: str | None = Field(
        default=None,
        description="Perplexity API key for deep research",
        alias="PERPLEXITY_API_KEY",
    )
    perplexity_enabled: bool = Field(
        default=True,
        description="Enable deep_research tool (requires API key)",
        alias="PERPLEXITY_ENABLED",
    )

    model_config = ConfigDict(populate_by_name=True)  # type: ignore[assignment,typeddict-unknown-key]


class GeminiSettings(BaseSettings):
    """Google Gemini API settings for final report generation"""

    api_key: str | None = Field(
        default=None, description="Google Gemini API key for report generation"
    )
    model: str = Field(
        default="gemini-2.0-flash-exp",
        description="Gemini model for final report generation",
    )
    enabled: bool = Field(
        default=False,
        description="Use Gemini for final report generation (requires API key)",
    )

    model_config = ConfigDict(env_prefix="GEMINI_")  # type: ignore[assignment,typeddict-unknown-key]


class AgentServiceSettings(BaseSettings):
    """Agent service connection settings"""

    url: str = Field(
        default="http://agent_service:8000",
        description="Agent service base URL",
        alias="AGENT_SERVICE_URL",
    )
    token: str = Field(
        default="",
        description="Service token for authenticating with agent-service",
        alias="RAG_SERVICE_TOKEN",
    )

    model_config = ConfigDict(populate_by_name=True)  # type: ignore[assignment,typeddict-unknown-key]


# Import LangfuseSettings from shared library to avoid duplication
import sys
from pathlib import Path

# Add parent directory to path to import shared
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.config.settings import LangfuseSettings  # noqa: E402


class Settings(BaseSettings):
    """Main RAG service settings"""

    environment: str = Field(
        default="development",
        description="Application environment (development, staging, production)",
    )
    port: int = Field(default=8002, description="Service port", alias="PORT")

    # Core settings
    llm: LLMSettings = Field(default_factory=LLMSettings)  # type: ignore[arg-type]
    cache: CacheSettings = Field(default_factory=CacheSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)  # type: ignore[arg-type]
    vector: VectorSettings = Field(default_factory=VectorSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    conversation: ConversationSettings = Field(default_factory=ConversationSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)
    agent_service: AgentServiceSettings = Field(default_factory=AgentServiceSettings)

    # Operational settings
    debug: bool = False
    log_level: str = "INFO"

    model_config = ConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8", populate_by_name=True
    )  # type: ignore[assignment,typeddict-unknown-key]


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings  # noqa: PLW0603
    if _settings is None:
        _settings = Settings()
    return _settings
