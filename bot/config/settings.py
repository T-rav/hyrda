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
        default="openai", description="LLM provider (only 'openai' is supported)"
    )
    api_key: SecretStr = Field(description="LLM API key")
    model: str = Field(default="gpt-4o-mini", description="LLM model name")
    base_url: str | None = Field(
        default=None, description="Custom base URL (for OpenAI-compatible APIs)"
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
    """MySQL database settings"""

    url: str = Field(
        default="mysql+pymysql://insightmesh_data:insightmesh_data_password@localhost:3306/insightmesh_data",
        description="MySQL connection URL",
    )
    enabled: bool = Field(default=True, description="Enable database features")

    model_config = ConfigDict(env_prefix="DATABASE_")  # type: ignore[assignment,typeddict-unknown-key]


class VectorSettings(BaseSettings):
    """Vector database settings for RAG (Qdrant)"""

    provider: str = Field(
        default="qdrant", description="Vector database provider (qdrant)"
    )
    collection_name: str = Field(
        default="insightmesh-knowledge-base", description="Collection name"
    )
    host: str = Field(default="localhost", description="Qdrant host")
    port: int = Field(default=6333, description="Qdrant REST API port")

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
        default=0.5, description="Final results minimum similarity threshold"
    )
    include_metadata: bool = Field(
        default=True, description="Include document metadata in context"
    )
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
        description="Enable adaptive query rewriting to improve retrieval accuracy",
    )
    query_rewrite_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model to use for query rewriting (fast model recommended)",
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

    # Prompt template settings
    use_prompt_templates: bool = Field(
        default=True,
        description="Use Langfuse prompt templates instead of hardcoded prompts",
    )
    system_prompt_template: str = Field(
        default="System/Default", description="Langfuse template name for system prompt"
    )
    prompt_template_version: str | None = Field(
        default=None,
        description="Specific prompt template version (uses latest if None)",
    )

    model_config = ConfigDict(env_prefix="LANGFUSE_")  # type: ignore[assignment,typeddict-unknown-key]


class Settings(BaseSettings):
    """Main application settings"""

    environment: str = Field(
        default="development",
        description="Application environment (development, staging, production)",
    )
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

    model_config = ConfigDict(
        env_file="../.env", extra="ignore", env_file_encoding="utf-8"
    )  # type: ignore[assignment,typeddict-unknown-key]
