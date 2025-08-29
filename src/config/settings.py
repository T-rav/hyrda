from pydantic import ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings


class SlackSettings(BaseSettings):
    """Slack API settings"""

    bot_token: str = Field(description="Slack bot token (xoxb-...)")
    app_token: str = Field(description="Slack app token (xapp-...)")
    bot_id: str = ""

    model_config = ConfigDict(env_prefix="SLACK_")


class LLMSettings(BaseSettings):
    """LLM API settings"""

    provider: str = Field(default="openai", description="LLM provider (openai, anthropic, ollama)")
    api_key: SecretStr = Field(description="LLM API key")
    model: str = Field(default="gpt-4o-mini", description="LLM model name")
    base_url: str | None = Field(default=None, description="Custom base URL (for ollama, etc.)")
    temperature: float = Field(default=0.7, description="Response temperature")
    max_tokens: int = Field(default=2000, description="Maximum response tokens")

    model_config = ConfigDict(env_prefix="LLM_")


class AgentSettings(BaseSettings):
    """Agent process settings"""

    enabled: bool = True

    model_config = ConfigDict(env_prefix="AGENT_")


class CacheSettings(BaseSettings):
    """Redis cache settings"""

    redis_url: str = Field(
        default="redis://localhost:6379", description="Redis connection URL"
    )
    conversation_ttl: int = Field(
        default=1800, description="Conversation cache TTL in seconds (30 minutes)"
    )
    enabled: bool = Field(default=True, description="Enable conversation caching")

    model_config = ConfigDict(env_prefix="CACHE_")


class DatabaseSettings(BaseSettings):
    """PostgreSQL database settings"""

    url: str = Field(description="PostgreSQL connection URL")
    enabled: bool = Field(default=True, description="Enable database features")

    model_config = ConfigDict(env_prefix="DATABASE_")


class VectorSettings(BaseSettings):
    """Vector database settings for RAG"""

    provider: str = Field(default="chroma", description="Vector DB provider (chroma, pinecone, pgvector)")
    url: str = Field(default="http://localhost:8000", description="Vector database URL")
    api_key: SecretStr | None = Field(default=None, description="Vector DB API key (if required)")
    collection_name: str = Field(default="knowledge_base", description="Collection/index name")
    enabled: bool = Field(default=True, description="Enable RAG functionality")

    model_config = ConfigDict(env_prefix="VECTOR_")


class EmbeddingSettings(BaseSettings):
    """Embedding model settings"""

    provider: str = Field(default="openai", description="Embedding provider (openai, sentence-transformers)")
    model: str = Field(default="text-embedding-3-small", description="Embedding model name")
    api_key: SecretStr | None = Field(default=None, description="Embedding API key (uses LLM key if None)")
    chunk_size: int = Field(default=1000, description="Text chunk size for embedding")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks")

    model_config = ConfigDict(env_prefix="EMBEDDING_")


class RAGSettings(BaseSettings):
    """RAG retrieval settings"""

    max_chunks: int = Field(default=5, description="Maximum chunks to retrieve")
    similarity_threshold: float = Field(default=0.7, description="Minimum similarity score")
    rerank_enabled: bool = Field(default=False, description="Enable result reranking")
    include_metadata: bool = Field(default=True, description="Include document metadata in context")

    model_config = ConfigDict(env_prefix="RAG_")


class Settings(BaseSettings):
    """Main application settings"""

    slack: SlackSettings = Field(default_factory=SlackSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    vector: VectorSettings = Field(default_factory=VectorSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    debug: bool = False
    log_level: str = "INFO"

    model_config = ConfigDict(env_file=".env", extra="ignore")
