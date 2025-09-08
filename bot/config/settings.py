from pydantic import ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings


class SlackSettings(BaseSettings):
    """Slack API settings"""

    bot_token: str = Field(description="Slack bot token (xoxb-...)")
    app_token: str = Field(description="Slack app token (xapp-...)")
    bot_id: str = ""

    model_config = ConfigDict(env_prefix="SLACK_")  # type: ignore[assignment,typeddict-unknown-key]


class LLMSettings(BaseSettings):
    """LLM API settings"""

    provider: str = Field(
        default="openai", description="LLM provider (openai, anthropic, ollama)"
    )
    api_key: SecretStr = Field(description="LLM API key")
    model: str = Field(default="gpt-4o-mini", description="LLM model name")
    base_url: str | None = Field(
        default=None, description="Custom base URL (for ollama, etc.)"
    )
    temperature: float = Field(default=0.7, description="Response temperature")
    max_tokens: int = Field(default=2000, description="Maximum response tokens")

    model_config = ConfigDict(env_prefix="LLM_")  # type: ignore[assignment,typeddict-unknown-key]


class AgentSettings(BaseSettings):
    """Agent process settings"""

    enabled: bool = True

    model_config = ConfigDict(env_prefix="AGENT_")  # type: ignore[assignment,typeddict-unknown-key]


class CacheSettings(BaseSettings):
    """Redis cache settings"""

    redis_url: str = Field(
        default="redis://localhost:6379", description="Redis connection URL"
    )
    conversation_ttl: int = Field(
        default=1800, description="Conversation cache TTL in seconds (30 minutes)"
    )
    enabled: bool = Field(default=True, description="Enable conversation caching")

    model_config = ConfigDict(env_prefix="CACHE_")  # type: ignore[assignment,typeddict-unknown-key]


class DatabaseSettings(BaseSettings):
    """PostgreSQL database settings"""

    url: str = Field(description="PostgreSQL connection URL")
    enabled: bool = Field(default=True, description="Enable database features")

    model_config = ConfigDict(env_prefix="DATABASE_")  # type: ignore[assignment,typeddict-unknown-key]


class VectorSettings(BaseSettings):
    """Vector database settings for RAG"""

    provider: str = Field(
        default="chroma", description="Vector DB provider (chroma, pinecone, pgvector)"
    )
    url: str = Field(default="http://localhost:8000", description="Vector database URL")
    api_key: SecretStr | None = Field(
        default=None, description="Vector DB API key (if required)"
    )
    collection_name: str = Field(
        default="knowledge_base", description="Collection/index name"
    )
    environment: str | None = Field(
        default=None, description="Pinecone environment (e.g., us-east-1-aws)"
    )
    enabled: bool = Field(default=True, description="Enable RAG functionality")

    model_config = ConfigDict(env_prefix="VECTOR_")  # type: ignore[assignment,typeddict-unknown-key]


class EmbeddingSettings(BaseSettings):
    """Embedding model settings"""

    provider: str = Field(
        default="openai",
        description="Embedding provider (openai, sentence-transformers)",
    )
    model: str = Field(
        default="text-embedding-3-small", description="Embedding model name"
    )
    api_key: SecretStr | None = Field(
        default=None, description="Embedding API key (uses LLM key if None)"
    )
    chunk_size: int = Field(default=1000, description="Text chunk size for embedding")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks")

    model_config = ConfigDict(env_prefix="EMBEDDING_")  # type: ignore[assignment,typeddict-unknown-key]


class RAGSettings(BaseSettings):
    """RAG retrieval settings"""

    max_chunks: int = Field(default=5, description="Maximum chunks to retrieve")
    similarity_threshold: float = Field(
        default=0.35, description="Minimum similarity score"
    )
    max_results: int = Field(default=5, description="Maximum final results to return")
    results_similarity_threshold: float = Field(
        default=0.7, description="Final results minimum similarity threshold"
    )
    rerank_enabled: bool = Field(default=False, description="Enable result reranking")
    include_metadata: bool = Field(
        default=True, description="Include document metadata in context"
    )

    model_config = ConfigDict(env_prefix="RAG_")  # type: ignore[assignment,typeddict-unknown-key]


class LangfuseSettings(BaseSettings):
    """Langfuse observability settings"""

    enabled: bool = Field(default=True, description="Enable Langfuse tracing")
    public_key: str = Field(default="", description="Langfuse public key")
    secret_key: SecretStr = Field(
        default=SecretStr(""), description="Langfuse secret key"
    )
    host: str = Field(
        default="https://cloud.langfuse.com", description="Langfuse host URL"
    )
    debug: bool = Field(default=False, description="Enable Langfuse debug logging")

    model_config = ConfigDict(env_prefix="LANGFUSE_")  # type: ignore[assignment,typeddict-unknown-key]


class Settings(BaseSettings):
    """Main application settings"""

    slack: SlackSettings = Field(default_factory=SlackSettings)  # type: ignore[arg-type]
    llm: LLMSettings = Field(default_factory=LLMSettings)  # type: ignore[arg-type]
    agent: AgentSettings = Field(default_factory=AgentSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)  # type: ignore[arg-type]
    vector: VectorSettings = Field(default_factory=VectorSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)
    debug: bool = False
    log_level: str = "INFO"

    model_config = ConfigDict(env_file="../.env", extra="ignore")  # type: ignore[assignment,typeddict-unknown-key]
